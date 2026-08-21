from database.connection import get_connection


VALID_ROLES = {"Athlete", "Coach"}
VALID_DECISIONS = {"Accepted", "Rejected"}


# ============================================================
# HELPERS
# ============================================================

def _clean_role(role):
    role = str(role or "").strip().title()

    if role not in VALID_ROLES:
        raise ValueError("Role must be Athlete or Coach.")

    return role


def _user_exists(cur, role, user_id):
    if role == "Athlete":
        cur.execute(
            """
            SELECT 1
            FROM athletes
            WHERE athlete_id = %s;
            """,
            (user_id,),
        )
    else:
        cur.execute(
            """
            SELECT 1
            FROM coaches
            WHERE coach_id = %s;
            """,
            (user_id,),
        )

    return cur.fetchone() is not None


def _already_connected(cur, athlete_id, coach_id):
    cur.execute(
        """
        SELECT 1
        FROM coach_athlete_mapping
        WHERE athlete_id = %s
          AND coach_id = %s;
        """,
        (athlete_id, coach_id),
    )

    return cur.fetchone() is not None


# ============================================================
# SEND CONNECTION REQUEST
# ============================================================

def send_connection_request(
    sender_role,
    sender_id,
    recipient_id,
    message=None,
):
    """
    Send a connection request.

    Athlete sender:
        sender_id = athlete_id
        recipient_id = coach_id

    Coach sender:
        sender_id = coach_id
        recipient_id = athlete_id

    Multiple requests to different people are allowed.

    A second Pending request between the same athlete and coach
    is blocked regardless of who originally sent the first request.
    """

    sender_role = _clean_role(sender_role)

    sender_id = str(sender_id or "").strip()
    recipient_id = str(recipient_id or "").strip()
    message = str(message or "").strip()

    if not sender_id:
        raise ValueError("Sender ID is required.")

    if not recipient_id:
        raise ValueError("Recipient ID is required.")

    if len(message) > 1000:
        raise ValueError(
            "Request message must be 1000 characters or fewer."
        )

    if sender_role == "Athlete":
        athlete_id = sender_id
        coach_id = recipient_id
        recipient_role = "Coach"

    else:
        coach_id = sender_id
        athlete_id = recipient_id
        recipient_role = "Athlete"

    conn = get_connection()
    cur = conn.cursor()

    try:
        # ----------------------------------------------------
        # Validate both users
        # ----------------------------------------------------
        if not _user_exists(
            cur,
            sender_role,
            sender_id,
        ):
            raise ValueError(
                f"{sender_role} ID '{sender_id}' does not exist."
            )

        if not _user_exists(
            cur,
            recipient_role,
            recipient_id,
        ):
            raise ValueError(
                f"{recipient_role} ID '{recipient_id}' does not exist."
            )

        # ----------------------------------------------------
        # Already connected
        # ----------------------------------------------------
        if _already_connected(
            cur,
            athlete_id,
            coach_id,
        ):
            raise ValueError(
                "This athlete and coach are already connected."
            )

        # ----------------------------------------------------
        # Duplicate pending request
        # ----------------------------------------------------
        cur.execute(
            """
            SELECT request_id, sender_role
            FROM connection_requests
            WHERE athlete_id = %s
              AND coach_id = %s
              AND status = 'Pending'
            LIMIT 1;
            """,
            (
                athlete_id,
                coach_id,
            ),
        )

        existing_request = cur.fetchone()

        if existing_request:
            raise ValueError(
                "A connection request between this athlete and "
                "coach is already pending."
            )

        # ----------------------------------------------------
        # Create request
        # ----------------------------------------------------
        cur.execute(
            """
            INSERT INTO connection_requests (
                athlete_id,
                coach_id,
                sender_role,
                message,
                status
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                'Pending'
            )
            RETURNING request_id;
            """,
            (
                athlete_id,
                coach_id,
                sender_role,
                message if message else None,
            ),
        )

        request_id = cur.fetchone()[0]

        # ----------------------------------------------------
        # Recipient notification
        # ----------------------------------------------------
        notification_message = (
            f"New connection request from "
            f"{sender_role} {sender_id}."
        )

        if message:
            notification_message += f" Message: {message}"

        cur.execute(
            """
            INSERT INTO notifications (
                request_id,
                recipient_role,
                recipient_id,
                notification_type,
                message,
                is_read
            )
            VALUES (
                %s,
                %s,
                %s,
                'Connection Request',
                %s,
                FALSE
            );
            """,
            (
                request_id,
                recipient_role,
                recipient_id,
                notification_message,
            ),
        )

        conn.commit()

        return request_id

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()


# ============================================================
# GET INCOMING PENDING REQUESTS
# ============================================================

def get_incoming_connection_requests(
    recipient_role,
    recipient_id,
):
    """
    Return Pending requests that this user must Accept or Reject.
    """

    recipient_role = _clean_role(recipient_role)
    recipient_id = str(recipient_id or "").strip()

    conn = get_connection()
    cur = conn.cursor()

    try:
        if recipient_role == "Athlete":
            cur.execute(
                """
                SELECT
                    cr.request_id,
                    cr.coach_id AS sender_id,
                    c.name AS sender_name,
                    cr.message,
                    cr.created_at
                FROM connection_requests cr
                JOIN coaches c
                    ON c.coach_id = cr.coach_id
                WHERE cr.athlete_id = %s
                  AND cr.sender_role = 'Coach'
                  AND cr.status = 'Pending'
                ORDER BY cr.created_at DESC;
                """,
                (recipient_id,),
            )

        else:
            cur.execute(
                """
                SELECT
                    cr.request_id,
                    cr.athlete_id AS sender_id,
                    a.name AS sender_name,
                    cr.message,
                    cr.created_at
                FROM connection_requests cr
                JOIN athletes a
                    ON a.athlete_id = cr.athlete_id
                WHERE cr.coach_id = %s
                  AND cr.sender_role = 'Athlete'
                  AND cr.status = 'Pending'
                ORDER BY cr.created_at DESC;
                """,
                (recipient_id,),
            )

        rows = cur.fetchall()

        return [
            {
                "request_id": row[0],
                "sender_id": row[1],
                "sender_name": row[2],
                "message": row[3],
                "created_at": row[4],
            }
            for row in rows
        ]

    finally:
        cur.close()
        conn.close()


# ============================================================
# ACCEPT / REJECT REQUEST
# ============================================================

def respond_to_connection_request(
    request_id,
    responder_role,
    responder_id,
    decision,
):
    """
    Accept or Reject a Pending request.

    Only the intended recipient can respond.

    Accepted:
        automatically creates coach_athlete_mapping.

    Accepted / Rejected:
        sender receives a notification.
    """

    responder_role = _clean_role(responder_role)
    responder_id = str(responder_id or "").strip()

    decision = str(decision or "").strip().title()

    if decision not in VALID_DECISIONS:
        raise ValueError(
            "Decision must be Accepted or Rejected."
        )

    conn = get_connection()
    cur = conn.cursor()

    try:
        # Lock request so two responses cannot happen simultaneously.
        cur.execute(
            """
            SELECT
                athlete_id,
                coach_id,
                sender_role,
                status
            FROM connection_requests
            WHERE request_id = %s
            FOR UPDATE;
            """,
            (request_id,),
        )

        row = cur.fetchone()

        if row is None:
            raise ValueError(
                "Connection request was not found."
            )

        athlete_id, coach_id, sender_role, status = row

        if status != "Pending":
            raise ValueError(
                f"This request has already been {status.lower()}."
            )

        # ----------------------------------------------------
        # Determine intended recipient
        # ----------------------------------------------------
        if sender_role == "Athlete":
            expected_responder_role = "Coach"
            expected_responder_id = coach_id

            sender_id = athlete_id
            sender_notification_role = "Athlete"

        else:
            expected_responder_role = "Athlete"
            expected_responder_id = athlete_id

            sender_id = coach_id
            sender_notification_role = "Coach"

        # ----------------------------------------------------
        # Security check
        # ----------------------------------------------------
        if (
            responder_role != expected_responder_role
            or responder_id != expected_responder_id
        ):
            raise PermissionError(
                "You are not authorised to respond to this request."
            )

        # ----------------------------------------------------
        # Update request
        # ----------------------------------------------------
        cur.execute(
            """
            UPDATE connection_requests
            SET
                status = %s,
                responded_at = CURRENT_TIMESTAMP
            WHERE request_id = %s;
            """,
            (
                decision,
                request_id,
            ),
        )

        # ----------------------------------------------------
        # ACCEPTED → create mapping
        # ----------------------------------------------------
        if decision == "Accepted":
            cur.execute(
                """
                INSERT INTO coach_athlete_mapping (
                    coach_id,
                    athlete_id
                )
                VALUES (%s, %s)
                ON CONFLICT (coach_id, athlete_id)
                DO NOTHING;
                """,
                (
                    coach_id,
                    athlete_id,
                ),
            )

        # ----------------------------------------------------
        # Notify original sender
        # ----------------------------------------------------
        notification_type = (
            "Request Accepted"
            if decision == "Accepted"
            else "Request Rejected"
        )

        notification_message = (
            f"{responder_role} {responder_id} "
            f"{decision.lower()} your connection request."
        )

        cur.execute(
            """
            INSERT INTO notifications (
                request_id,
                recipient_role,
                recipient_id,
                notification_type,
                message,
                is_read
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                FALSE
            );
            """,
            (
                request_id,
                sender_notification_role,
                sender_id,
                notification_type,
                notification_message,
            ),
        )

        conn.commit()

        return {
            "request_id": request_id,
            "status": decision,
            "athlete_id": athlete_id,
            "coach_id": coach_id,
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()


# ============================================================
# NOTIFICATIONS
# ============================================================

def get_notifications(
    recipient_role,
    recipient_id,
    limit=50,
):
    recipient_role = _clean_role(recipient_role)
    recipient_id = str(recipient_id or "").strip()

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT
                notification_id,
                request_id,
                notification_type,
                message,
                is_read,
                created_at
            FROM notifications
            WHERE recipient_role = %s
              AND recipient_id = %s
            ORDER BY created_at DESC
            LIMIT %s;
            """,
            (
                recipient_role,
                recipient_id,
                int(limit),
            ),
        )

        rows = cur.fetchall()

        return [
            {
                "notification_id": row[0],
                "request_id": row[1],
                "notification_type": row[2],
                "message": row[3],
                "is_read": row[4],
                "created_at": row[5],
            }
            for row in rows
        ]

    finally:
        cur.close()
        conn.close()


def get_unread_notification_count(
    recipient_role,
    recipient_id,
):
    recipient_role = _clean_role(recipient_role)
    recipient_id = str(recipient_id or "").strip()

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM notifications
            WHERE recipient_role = %s
              AND recipient_id = %s
              AND is_read = FALSE;
            """,
            (
                recipient_role,
                recipient_id,
            ),
        )

        return int(cur.fetchone()[0])

    finally:
        cur.close()
        conn.close()


def mark_notification_read(
    notification_id,
    recipient_role,
    recipient_id,
):
    recipient_role = _clean_role(recipient_role)
    recipient_id = str(recipient_id or "").strip()

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            UPDATE notifications
            SET is_read = TRUE
            WHERE notification_id = %s
              AND recipient_role = %s
              AND recipient_id = %s;
            """,
            (
                notification_id,
                recipient_role,
                recipient_id,
            ),
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()


def mark_all_notifications_read(
    recipient_role,
    recipient_id,
):
    recipient_role = _clean_role(recipient_role)
    recipient_id = str(recipient_id or "").strip()

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            UPDATE notifications
            SET is_read = TRUE
            WHERE recipient_role = %s
              AND recipient_id = %s
              AND is_read = FALSE;
            """,
            (
                recipient_role,
                recipient_id,
            ),
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()


# ============================================================
# SENT REQUEST HISTORY
# ============================================================

def get_sent_connection_requests(
    sender_role,
    sender_id,
):
    sender_role = _clean_role(sender_role)
    sender_id = str(sender_id or "").strip()

    conn = get_connection()
    cur = conn.cursor()

    try:
        if sender_role == "Athlete":
            cur.execute(
                """
                SELECT
                    cr.request_id,
                    cr.coach_id,
                    c.name,
                    cr.message,
                    cr.status,
                    cr.created_at,
                    cr.responded_at
                FROM connection_requests cr
                JOIN coaches c
                    ON c.coach_id = cr.coach_id
                WHERE cr.athlete_id = %s
                  AND cr.sender_role = 'Athlete'
                ORDER BY cr.created_at DESC;
                """,
                (sender_id,),
            )

        else:
            cur.execute(
                """
                SELECT
                    cr.request_id,
                    cr.athlete_id,
                    a.name,
                    cr.message,
                    cr.status,
                    cr.created_at,
                    cr.responded_at
                FROM connection_requests cr
                JOIN athletes a
                    ON a.athlete_id = cr.athlete_id
                WHERE cr.coach_id = %s
                  AND cr.sender_role = 'Coach'
                ORDER BY cr.created_at DESC;
                """,
                (sender_id,),
            )

        rows = cur.fetchall()

        return [
            {
                "request_id": row[0],
                "recipient_id": row[1],
                "recipient_name": row[2],
                "message": row[3],
                "status": row[4],
                "created_at": row[5],
                "responded_at": row[6],
            }
            for row in rows
        ]

    finally:
        cur.close()
        conn.close()
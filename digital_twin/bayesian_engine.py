def bayesian_update(prior_probability, likelihood, evidence_probability):
    """
    Bayes' theorem:
    P(H|D) = P(D|H) * P(H) / P(D)

    prior_probability = previous belief about high fatigue/injury
    likelihood = probability of observing current data if risk is high
    evidence_probability = overall probability of observing this data
    """

    try:
        posterior = (likelihood * prior_probability) / evidence_probability
        return round(max(0, min(1, posterior)), 3)
    except Exception:
        return round(prior_probability, 3)


def estimate_fatigue_prior(previous_state):
    """
    Uses previous Digital Twin state as prior belief.
    """

    if previous_state is None:
        return 0.50

    fatigue_score = previous_state.get("fatigue_score", 50)

    try:
        return round(float(fatigue_score) / 100, 3)
    except Exception:
        return 0.50


def estimate_fatigue_likelihood(current_row):
    """
    Estimates likelihood from current Digital Twin signals.
    """

    fatigue_score = float(current_row.get("fatigue_score", 50)) / 100
    training_load = min(float(current_row.get("training_load", 50)) / 150, 1)
    recovery_index = float(current_row.get("recovery_index", 0.6))

    likelihood = (
        fatigue_score * 0.50
        + training_load * 0.30
        + (1 - recovery_index) * 0.20
    )

    return round(max(0.05, min(0.95, likelihood)), 3)


def apply_bayesian_fatigue_update(df, previous_state):
    """
    Adds Bayesian updated fatigue probability to the Digital Twin state.
    """

    df = df.copy()

    prior = estimate_fatigue_prior(previous_state)

    updated_probs = []

    for _, row in df.iterrows():
        likelihood = estimate_fatigue_likelihood(row)

        posterior = bayesian_update(
            prior_probability=prior,
            likelihood=likelihood,
            evidence_probability=0.50,
        )

        updated_probs.append(posterior)

        prior = posterior

    df["bayesian_fatigue_probability"] = updated_probs

    return df
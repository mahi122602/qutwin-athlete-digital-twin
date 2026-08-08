from dataclasses import dataclass
import pandas as pd

from digital_twin.history_engine import compare_with_previous_state


@dataclass
class AthleteTwin:
    athlete_id: str
    current_state: pd.DataFrame
    previous_state: dict | None = None

    def apply_memory(self) -> pd.DataFrame:
        df = self.current_state.copy()

        trend_rows = []

        for _, row in df.iterrows():
            trend_data = compare_with_previous_state(
                current_row=row,
                previous_row=self.previous_state
            )
            trend_rows.append(trend_data)

        trend_df = pd.DataFrame(trend_rows)
        df = pd.concat([df.reset_index(drop=True), trend_df.reset_index(drop=True)], axis=1)

        return df

    def latest_summary(self):
        latest = self.current_state.iloc[-1]

        return {
            "athlete_id": self.athlete_id,
            "twin_score": latest.get("twin_score"),
            "athlete_state": latest.get("athlete_state"),
            "fatigue_index": latest.get("fatigue_index"),
            "readiness_index": latest.get("readiness_index"),
            "recovery_index": latest.get("recovery_index"),
            "state_explanation": latest.get("state_explanation"),
        }
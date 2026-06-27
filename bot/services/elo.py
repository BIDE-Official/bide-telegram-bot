K = 32
MIN_DELTA = K // 16
MULTIPLIERS = {"win": 1, "mars": 2}


def expected(rating_a: int, rating_b: int) -> float:
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def delta(rating_winner: int, rating_loser: int, result: str) -> int:
    m = MULTIPLIERS.get(result, 1)
    raw = K * (1 - expected(rating_winner, rating_loser)) * m
    return max(round(raw), MIN_DELTA)


def predict(rating_a: int, rating_b: int) -> dict[str, int]:
    e_a = expected(rating_a, rating_b)
    e_b = 1 - e_a

    return {
        "win": max(round(K * (1 - e_a) * 1), MIN_DELTA),
        "mars": max(round(K * (1 - e_a) * 2), MIN_DELTA),
        "loss": -max(round(K * (1 - e_b) * 1), MIN_DELTA),
        "loss_mars": -max(round(K * (1 - e_b) * 2), MIN_DELTA),
    }

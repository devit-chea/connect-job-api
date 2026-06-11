def parse_verify_key(key: str):
    if not key:
        return None
    return key.replace(r"\n", "\n")

def parse_sentinels(value: str):
    if value is None:
        return []

    sentinels = []
    for item in value.split(","):
        host, port = item.strip().split(":")
        sentinels.append((host, int(port)))
    return sentinels

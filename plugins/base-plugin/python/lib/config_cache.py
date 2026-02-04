"""The real config_cache module that hooks need to import."""


def get_config() -> dict:
    return {"loaded": True, "source": "base-plugin"}

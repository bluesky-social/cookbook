def parse_full_aturi(uri: str) -> tuple[str, str, str]:
	if not uri.startswith("at://"):
		raise ValueError("Invalid AT URI: missing at:// prefix")
	if uri.count("/") != 4:
		raise ValueError("Invalid AT URI: expected format at://repo/collection/rkey")
	repo, collection, rkey = uri.removeprefix("at://").split("/")
	return repo, collection, rkey

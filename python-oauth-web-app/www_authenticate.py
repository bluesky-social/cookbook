import urllib.request

def parse_www_authenticate(data: str):
	scheme, _, params = data.partition(" ")
	items = urllib.request.parse_http_list(params)
	opts = urllib.request.parse_keqv_list(items)
	return scheme, opts

if __name__ == "__main__":
	print(parse_www_authenticate('DPoP algs="RS256 RS384 RS512 PS256 PS384 PS512 ES256 ES256K ES384 ES512", error="use_dpop_nonce"'))

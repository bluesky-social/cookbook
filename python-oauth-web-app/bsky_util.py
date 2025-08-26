import re


# only supports hashtags, for now
def extract_facets(text: str) -> list:
    parts = re.split(
        r"(#\w+?\b)", text
    )  # always an odd-length list, with at least one item
    start_idx = len(parts[0].encode())
    facets = []
    for hashtag, plaintext in zip(parts[1::2], parts[2::2]):
        taglen, textlen = len(hashtag.encode()), len(plaintext.encode())
        facets.append(
            {
                "index": {"byteStart": start_idx, "byteEnd": start_idx + taglen},
                "features": [
                    {"$type": "app.bsky.richtext.facet#tag", "tag": hashtag[1:]}
                ],
            }
        )
        start_idx += taglen + textlen
    return facets


if __name__ == "__main__":
    assert extract_facets("hello world") == []

    assert extract_facets("this is # not a hashtag but #ThisIs") == [
        {
            "index": {"byteStart": 28, "byteEnd": 35},
            "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": "ThisIs"}],
        }
    ]

    assert extract_facets(
        "this #message #has #farTooMany #hashtags and also more #words after"
    ) == [
        {
            "index": {"byteStart": 5, "byteEnd": 13},
            "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": "message"}],
        },
        {
            "index": {"byteStart": 14, "byteEnd": 18},
            "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": "has"}],
        },
        {
            "index": {"byteStart": 19, "byteEnd": 30},
            "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": "farTooMany"}],
        },
        {
            "index": {"byteStart": 31, "byteEnd": 40},
            "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": "hashtags"}],
        },
        {
            "index": {"byteStart": 55, "byteEnd": 61},
            "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": "words"}],
        },
    ]

package main

import (
	"fmt"
	"regexp"
)

var hashtagRegex = regexp.MustCompile(`#\w+?\b`)

// TODO: support more than just hashtags!
func parseFacets(text string) []map[string]any {
	var res []map[string]any
	for _, match := range hashtagRegex.FindAllStringSubmatchIndex(text, -1) {
		fmt.Println(match)
		res = append(res, map[string]any{
			"index": map[string]any{
				"byteStart": match[0],
				"byteEnd":   match[1],
			},
			"features": []map[string]any{
				{
					"$type": "app.bsky.richtext.facet#tag",
					"tag":   text[match[0]+1 : match[1]],
				},
			},
		})
	}
	return res
}


Download and Inspect Repository (Go)
====================================

This is a small helper utility to download atproto repositories as a CAR file, and then unpack contents to JSON files in a directory.

## Install

You need the Go programming language toolchain installed: <https://go.dev/doc/install>

You can directly install and run the command (without a git checkout):

```shell
go install github.com/bluesky-social/cookbook/go-repo-export@latest

go-export-repo [...]
```

Or you can clone this repository and build locally:

```shell
git clone https://github.com/bluesky-social/cookbook
cd cookbook/go-repo-export
go build ./...

./go-export-repo [...]
```

## Commands

There are three commands:

```shell
go-export-repo download <at-identifier>
go-export-repo ls <did.car>
go-export-repo unpack <did.car>
```

For example:

```shell
> go-export-repo download atproto.com
resolving identity: atproto.com
downloading from https://bsky.social to: did:plc:ewvi7nxzyoun6zhxrhs64oiz.car

> go-export-repo ls did:plc:ewvi7nxzyoun6zhxrhs64oiz.car
=== did:plc:ewvi7nxzyoun6zhxrhs64oiz ===
key	record_cid
app.bsky.actor.profile/self	bafyreifbxwvk2ewuduowdjkkjgspiy5li2dzyycrnlbu27gn3hfgthez3u
app.bsky.feed.like/3jucagnrmn22x	bafyreieohq4ngetnrpse22mynxpinzfnaw6m5xcsjj3s4oiidjlnnfo76a
app.bsky.feed.like/3jucahkymkk2e	bafyreidqrmqvrnz52efgqfavvjdbwob3bc2g3vvgmhmexgx4xputjty754
app.bsky.feed.like/3jucaj3qgmk2h	bafyreig5c2atahtzr2vo4v64aovgqbv6qwivfwf3ex5gn2537wwmtnkm3e
app.bsky.feed.like/3jucak5thpc24	bafyreihxmwu5qrh6ktyo2f6jht632cr7yxrx6qikeoapqakesrxlkbzjje
app.bsky.feed.like/3jucaow7dzl2k	bafyreidyhsstqem43nevh65u6dolhbxmwllpbetdb7psznjl6k4w6oonem
app.bsky.feed.like/3jucavec76l2k	bafyreifjtco4uqas7lz7lhkrwp76erbr4gt6akh6hfcnre7exgsn2pdyru
app.bsky.feed.like/3jucb2d7ojs2g	bafyreibobswhj7by2j475wtnbtknrbdxwjndb2mdjs74bhy6k3n26fw4hm
[...]

> go-export-repo unpack did:plc:ewvi7nxzyoun6zhxrhs64oiz.car
writing output to: did:plc:ewvi7nxzyoun6zhxrhs64oiz
did:plc:ewvi7nxzyoun6zhxrhs64oiz/app.bsky.actor.profile/self.json
did:plc:ewvi7nxzyoun6zhxrhs64oiz/app.bsky.feed.like/3jucagnrmn22x.json
did:plc:ewvi7nxzyoun6zhxrhs64oiz/app.bsky.feed.like/3jucahkymkk2e.json
did:plc:ewvi7nxzyoun6zhxrhs64oiz/app.bsky.feed.like/3jucaj3qgmk2h.json
did:plc:ewvi7nxzyoun6zhxrhs64oiz/app.bsky.feed.like/3jucak5thpc24.json
did:plc:ewvi7nxzyoun6zhxrhs64oiz/app.bsky.feed.like/3jucaow7dzl2k.json
did:plc:ewvi7nxzyoun6zhxrhs64oiz/app.bsky.feed.like/3jucavec76l2k.json
did:plc:ewvi7nxzyoun6zhxrhs64oiz/app.bsky.feed.like/3jucb2d7ojs2g.json
did:plc:ewvi7nxzyoun6zhxrhs64oiz/app.bsky.feed.like/3jucb2tkqss2e.json
[...]

> ls did:plc:ewvi7nxzyoun6zhxrhs64oiz
app.bsky.actor.profile  app.bsky.feed.post    app.bsky.graph.follow
app.bsky.feed.like      app.bsky.feed.repost  _commit.json
```

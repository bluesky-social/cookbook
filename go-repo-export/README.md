
Download and Inspect Repository (Go)
====================================

This is a small helper utility to download atproto repositories as a CAR file, and then unpack contents to JSON files in a directory.

## Install

You need the Go programming language toolchain installed: <https://go.dev/doc/install>

You can directly install and run the command (without a git checkout):

```shell
go install github.com/bluesky-social/cookbook/go-repo-export@latest

go-repo-export [...]
```

Or you can clone this repository and build locally:

```shell
git clone https://github.com/bluesky-social/cookbook
cd cookbook/go-repo-export
go build ./...

./go-repo-export [...]
```

## Commands

Commands which talk to the target account's PDS instance:

```shell
go-repo-export download-repo <at-identifier>
go-repo-export list-blobs <at-identifier>
go-repo-export download-blobs <at-identifier>
```

Which work with a local repo CAR file:

```shell
go-repo-export list-records <did.car>
go-repo-export unpack-records <did.car>
```

For example:

```shell
> ./go-repo-export download-repo atproto.com
resolving identity: atproto.com
downloading from https://bsky.social to: did:plc:ewvi7nxzyoun6zhxrhs64oiz.car

> ./go-repo-export list-records did:plc:ewvi7nxzyoun6zhxrhs64oiz.car
=== did:plc:ewvi7nxzyoun6zhxrhs64oiz ===
key	record_cid
app.bsky.actor.profile/self	bafyreifbxwvk2ewuduowdjkkjgspiy5li2dzyycrnlbu27gn3hfgthez3u
app.bsky.feed.like/3jucagnrmn22x	bafyreieohq4ngetnrpse22mynxpinzfnaw6m5xcsjj3s4oiidjlnnfo76a
app.bsky.feed.like/3jucahkymkk2e	bafyreidqrmqvrnz52efgqfavvjdbwob3bc2g3vvgmhmexgx4xputjty754
app.bsky.feed.like/3jucaj3qgmk2h	bafyreig5c2atahtzr2vo4v64aovgqbv6qwivfwf3ex5gn2537wwmtnkm3e
[...]

> ./go-repo-export unpack-records did:plc:ewvi7nxzyoun6zhxrhs64oiz.car
writing output to: did:plc:ewvi7nxzyoun6zhxrhs64oiz
did:plc:ewvi7nxzyoun6zhxrhs64oiz/app.bsky.actor.profile/self.json
did:plc:ewvi7nxzyoun6zhxrhs64oiz/app.bsky.feed.like/3jucagnrmn22x.json
did:plc:ewvi7nxzyoun6zhxrhs64oiz/app.bsky.feed.like/3jucahkymkk2e.json
did:plc:ewvi7nxzyoun6zhxrhs64oiz/app.bsky.feed.like/3jucaj3qgmk2h.json
[...]

> ls did:plc:ewvi7nxzyoun6zhxrhs64oiz
app.bsky.actor.profile  app.bsky.feed.post    app.bsky.graph.follow
app.bsky.feed.like      app.bsky.feed.repost  _commit.json

> ./go-repo-export list-blobs atproto.com
bafkreiacrjijybmsgnq3mca6fvhtvtc7jdtjflomoenrh4ph77kghzkiii
bafkreib4xwiqhxbqidwwatoqj7mrx6mr7wlc5s6blicq5wq2qsq37ynx5y
bafkreibdnsisdacjv3fswjic4dp7tju7mywfdlcrpleisefvzf44c3p7wm
bafkreiebtvblnu4jwu66y57kakido7uhiigenznxdlh6r6wiswblv5m4py
[...]

> ./go-repo-export download-blobs atproto.com
writing blobs to: did:plc:ewvi7nxzyoun6zhxrhs64oiz/_blob
did:plc:ewvi7nxzyoun6zhxrhs64oiz/_blob/bafkreiacrjijybmsgnq3mca6fvhtvtc7jdtjflomoenrh4ph77kghzkiii	downloaded
did:plc:ewvi7nxzyoun6zhxrhs64oiz/_blob/bafkreib4xwiqhxbqidwwatoqj7mrx6mr7wlc5s6blicq5wq2qsq37ynx5y	downloaded
did:plc:ewvi7nxzyoun6zhxrhs64oiz/_blob/bafkreibdnsisdacjv3fswjic4dp7tju7mywfdlcrpleisefvzf44c3p7wm	downloaded
[...]
```

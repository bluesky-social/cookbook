#!/usr/bin/env bash

set -o pipefail
set -e
set -u

go build .
./go-repo-export download-repo atproto.com
./go-repo-export list-records did:plc:ewvi7nxzyoun6zhxrhs64oiz.car
./go-repo-export unpack-records did:plc:ewvi7nxzyoun6zhxrhs64oiz.car
./go-repo-export list-blobs atproto.com
./go-repo-export list-blobs did:plc:ewvi7nxzyoun6zhxrhs64oiz
./go-repo-export download-blobs atproto.com

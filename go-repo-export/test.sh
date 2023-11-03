#!/usr/bin/env bash

set -o pipefail
set -e
set -u

go build .
./go-export-repo download-repo atproto.com
./go-export-repo list-records did:plc:ewvi7nxzyoun6zhxrhs64oiz.car
./go-export-repo unpack-records did:plc:ewvi7nxzyoun6zhxrhs64oiz.car
./go-export-repo list-blobs atproto.com
./go-export-repo list-blobs did:plc:ewvi7nxzyoun6zhxrhs64oiz
./go-export-repo download-blobs atproto.com

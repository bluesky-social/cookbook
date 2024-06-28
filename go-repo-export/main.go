package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	comatproto "github.com/bluesky-social/indigo/api/atproto"
	_ "github.com/bluesky-social/indigo/api/bsky"
	_ "github.com/bluesky-social/indigo/api/chat"
	_ "github.com/bluesky-social/indigo/api/ozone"
	"github.com/bluesky-social/indigo/atproto/identity"
	"github.com/bluesky-social/indigo/atproto/syntax"
	"github.com/bluesky-social/indigo/repo"
	"github.com/bluesky-social/indigo/xrpc"
	"github.com/ipfs/go-cid"
)

func main() {
	if err := run(); err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		os.Exit(1)
	}
}

func run() error {
	if len(os.Args) != 3 {
		return fmt.Errorf("expected two args: <command> <target>")
	}
	switch os.Args[1] {
	case "download-repo":
		return carDownload(os.Args[2])
	case "list-records":
		return carList(os.Args[2])
	case "unpack-records":
		return carUnpack(os.Args[2])
	case "list-blobs":
		return blobList(os.Args[2])
	case "download-blobs":
		return blobDownloadAll(os.Args[2])
	default:
		return fmt.Errorf("unexpected command: %s", os.Args[1])
	}
}

func carDownload(raw string) error {
	ctx := context.Background()
	atid, err := syntax.ParseAtIdentifier(raw)
	if err != nil {
		return err
	}

	// first look up the DID and PDS for this repo
	fmt.Printf("resolving identity: %s\n", atid.String())
	dir := identity.DefaultDirectory()
	ident, err := dir.Lookup(ctx, *atid)
	if err != nil {
		return err
	}

	// create a new API client to connect to the account's PDS
	xrpcc := xrpc.Client{
		Host: ident.PDSEndpoint(),
	}
	if xrpcc.Host == "" {
		return fmt.Errorf("no PDS endpoint for identity")
	}

	carPath := ident.DID.String() + ".car"
	fmt.Printf("downloading from %s to: %s\n", xrpcc.Host, carPath)
	repoBytes, err := comatproto.SyncGetRepo(ctx, &xrpcc, ident.DID.String(), "")
	if err != nil {
		return err
	}
	return os.WriteFile(carPath, repoBytes, 0666)
}

func carList(carPath string) error {
	ctx := context.Background()
	fi, err := os.Open(carPath)
	if err != nil {
		return err
	}

	// read repository tree in to memory
	r, err := repo.ReadRepoFromCar(ctx, fi)
	if err != nil {
		return err
	}

	// extract DID from repo commit
	sc := r.SignedCommit()
	did, err := syntax.ParseDID(sc.Did)
	if err != nil {
		return err
	}

	fmt.Printf("=== %s ===\n", did)
	fmt.Println("key\trecord_cid")

	err = r.ForEach(ctx, "", func(k string, v cid.Cid) error {
		fmt.Printf("%s\t%s\n", k, v.String())
		return nil
	})
	if err != nil {
		return err
	}
	return nil
}

func carUnpack(carPath string) error {
	ctx := context.Background()
	fi, err := os.Open(carPath)
	if err != nil {
		return err
	}

	r, err := repo.ReadRepoFromCar(ctx, fi)
	if err != nil {
		return err
	}

	// extract DID from repo commit
	sc := r.SignedCommit()
	did, err := syntax.ParseDID(sc.Did)
	if err != nil {
		return err
	}

	topDir := did.String()
	fmt.Printf("writing output to: %s\n", topDir)

	// first the commit object as a meta file
	commitPath := topDir + "/_commit"
	os.MkdirAll(filepath.Dir(commitPath), os.ModePerm)
	recJson, err := json.MarshalIndent(sc, "", "  ")
	if err != nil {
		return err
	}
	if err := os.WriteFile(commitPath+".json", recJson, 0666); err != nil {
		return err
	}

	// then all the actual records
	err = r.ForEach(ctx, "", func(k string, v cid.Cid) error {
		_, rec, err := r.GetRecord(ctx, k)
		if err != nil {
			return err
		}

		recPath := topDir + "/" + k
		fmt.Printf("%s.json\n", recPath)
		os.MkdirAll(filepath.Dir(recPath), os.ModePerm)
		if err != nil {
			return err
		}
		recJson, err := json.MarshalIndent(rec, "", "  ")
		if err != nil {
			return err
		}
		if err := os.WriteFile(recPath+".json", recJson, 0666); err != nil {
			return err
		}

		return nil
	})
	if err != nil {
		return err
	}
	return nil
}

func blobList(raw string) error {
	ctx := context.Background()
	atid, err := syntax.ParseAtIdentifier(raw)
	if err != nil {
		return err
	}

	// first look up the DID and PDS for this repo
	dir := identity.DefaultDirectory()
	ident, err := dir.Lookup(ctx, *atid)
	if err != nil {
		return err
	}

	// create a new API client to connect to the account's PDS
	xrpcc := xrpc.Client{
		Host: ident.PDSEndpoint(),
	}
	if xrpcc.Host == "" {
		return fmt.Errorf("no PDS endpoint for identity")
	}

	cursor := ""
	for {
		resp, err := comatproto.SyncListBlobs(ctx, &xrpcc, cursor, ident.DID.String(), 500, "")
		if err != nil {
			return err
		}
		for _, cidStr := range resp.Cids {
			fmt.Println(cidStr)
		}
		if resp.Cursor != nil && *resp.Cursor != "" {
			cursor = *resp.Cursor
		} else {
			break
		}
	}
	return nil
}

func blobDownloadAll(raw string) error {
	ctx := context.Background()
	atid, err := syntax.ParseAtIdentifier(raw)
	if err != nil {
		return err
	}

	// first look up the DID and PDS for this repo
	dir := identity.DefaultDirectory()
	ident, err := dir.Lookup(ctx, *atid)
	if err != nil {
		return err
	}

	// create a new API client to connect to the account's PDS
	xrpcc := xrpc.Client{
		Host: ident.PDSEndpoint(),
	}
	if xrpcc.Host == "" {
		return fmt.Errorf("no PDS endpoint for identity")
	}

	topDir := ident.DID.String() + "/_blob"
	fmt.Printf("writing blobs to: %s\n", topDir)
	os.MkdirAll(topDir, os.ModePerm)

	cursor := ""
	for {
		resp, err := comatproto.SyncListBlobs(ctx, &xrpcc, cursor, ident.DID.String(), 500, "")
		if err != nil {
			return err
		}
		for _, cidStr := range resp.Cids {
			blobPath := topDir + "/" + cidStr
			if _, err := os.Stat(blobPath); err == nil {
				fmt.Printf("%s\texists\n", blobPath)
				continue
			}
			blobBytes, err := comatproto.SyncGetBlob(ctx, &xrpcc, cidStr, ident.DID.String())
			if err != nil {
				return err
			}
			if err := os.WriteFile(blobPath, blobBytes, 0666); err != nil {
				return err
			}
			fmt.Printf("%s\tdownloaded\n", blobPath)
		}
		if resp.Cursor != nil && *resp.Cursor != "" {
			cursor = *resp.Cursor
		} else {
			break
		}
	}
	return nil
}

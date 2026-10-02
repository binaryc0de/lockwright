// Command flagcalc prints a session's per-instance flag from the platform's
// secret file. DEV/TEST ONLY (tools/m3_smoke.sh without Docker): anyone who
// can read the secret file can do this anyway; never ship it in a deploy.
//
//	go run ./platform/cmd/flagcalc -secret data/secret.key -session ID -challenge intranet -format 'FLAG{{{nonce}}}'
package main

import (
	"flag"
	"fmt"
	"os"

	"github.com/binaryc0de/escapebox/platform/internal/flags"
)

func main() {
	secretPath := flag.String("secret", "data/secret.key", "platform secret file")
	session := flag.String("session", "", "session id")
	challenge := flag.String("challenge", "", "challenge id")
	format := flag.String("format", "FLAG{{{nonce}}}", "flag format from room.yaml")
	flag.Parse()
	secret, err := os.ReadFile(*secretPath)
	if err != nil || *session == "" || *challenge == "" {
		fmt.Fprintln(os.Stderr, "usage: flagcalc -secret FILE -session ID -challenge ID [-format F]", err)
		os.Exit(2)
	}
	fmt.Println(flags.PerInstance(secret, *session, *challenge, *format))
}

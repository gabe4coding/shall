package partners

import (
	"bytes"
	"net/http"
)

func Push(url string, body []byte) (*http.Response, error) {
	return http.Post(url, "application/json", bytes.NewReader(body))
}

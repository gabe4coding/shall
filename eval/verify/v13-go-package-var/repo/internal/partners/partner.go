package partners

import (
	"bytes"
	"net/http"

	"github.com/tf/booking/internal/httpx"
)

var client = httpx.New()

func Push(url string, body []byte) (*http.Response, error) {
	return client.Post(url, "application/json", bytes.NewReader(body))
}

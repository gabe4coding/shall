package httpx

import (
	"net/http"
	"time"
)

// New returns the client every outbound call must use.
func New() *http.Client {
	return &http.Client{Timeout: 3 * time.Second}
}

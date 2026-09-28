package main

import "github.com/tf/booking/internal/partners"

func main() {
	if _, err := partners.Push("https://partner.example/slots", nil); err != nil {
		panic(err)
	}
}

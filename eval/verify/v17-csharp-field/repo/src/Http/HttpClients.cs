using System;
using System.Net.Http;

namespace Booking.Http;

public static class HttpClients
{
    public static HttpClient Partner() => new HttpClient
    {
        BaseAddress = new Uri("https://partner.example"),
        Timeout = TimeSpan.FromSeconds(3),
    };
}

using System.Net.Http;
using System.Threading.Tasks;
using Booking.Http;

namespace Booking.Partners;

public class PartnerSync
{
    private readonly HttpClient _client = HttpClients.Partner();

    public Task PushAsync(string json) =>
        _client.PutAsync("/slots", new StringContent(json));
}

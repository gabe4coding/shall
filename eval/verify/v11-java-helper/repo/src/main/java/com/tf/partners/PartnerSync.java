package com.tf.partners;

import com.tf.http.Requests;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpResponse;

public class PartnerSync {

    private static final URI PARTNER_URI = URI.create("https://partner.example/slots");
    private final HttpClient client = HttpClient.newHttpClient();

    public void push(String body) throws Exception {
        client.send(Requests.put(PARTNER_URI, body), HttpResponse.BodyHandlers.discarding());
    }
}

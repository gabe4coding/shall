package com.tf.http;

import java.net.URI;
import java.net.http.HttpRequest;
import java.time.Duration;

public final class Requests {

    private static final Duration DEFAULT_TIMEOUT = Duration.ofSeconds(3);

    private Requests() {
    }

    public static HttpRequest get(URI uri) {
        return HttpRequest.newBuilder(uri)
                .timeout(DEFAULT_TIMEOUT)
                .GET()
                .build();
    }

    public static HttpRequest put(URI uri, String body) {
        return HttpRequest.newBuilder(uri)
                .timeout(DEFAULT_TIMEOUT)
                .PUT(HttpRequest.BodyPublishers.ofString(body))
                .build();
    }
}

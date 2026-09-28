package com.tf.http

import okhttp3.OkHttpClient
import java.time.Duration

object Clients {
    val partner: OkHttpClient = OkHttpClient.Builder()
        .callTimeout(Duration.ofSeconds(3))
        .build()
}

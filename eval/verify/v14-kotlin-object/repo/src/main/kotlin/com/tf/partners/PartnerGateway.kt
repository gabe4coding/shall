package com.tf.partners

import com.tf.http.Clients
import okhttp3.Request

class PartnerGateway {
    fun push(url: String) {
        Clients.partner.newCall(Request.Builder().url(url).build()).execute().close()
    }
}

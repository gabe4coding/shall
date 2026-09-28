"""Language-generic pieces of the code graph (no network, no model)."""

import pytest

from jrfc.codegraph import normalize_chain, parse_import


@pytest.mark.parametrize("text, chain", [
    ("await new LegacyClient(url).send", "LegacyClient.send"),
    ("$this->client->post", "client.post"),
    ("self.client.post(id).send", "client.post.send"),
    ("ClientFactory::partner()->put", "ClientFactory.partner.put"),
    ("this.api.getJson<Review[]>", "api.getJson"),
    ("@connection.put", "connection.put"),
    ("user?.profile?.load", "user.profile.load"),
])
def test_normalize_chain(text, chain):
    assert normalize_chain(text) == chain


@pytest.mark.parametrize("statement, expected", [
    ('import { request, other as o } from "../http/client";',
     [("request", "request", "../http/client"), ("o", "other", "../http/client")]),
    ('import axios from "axios";', [("axios", None, "axios")]),
    ("from payments.http import make_session", [("make_session", "make_session", "payments.http")]),
    ("from . import provider", [("provider", "provider", ".")]),
    ("import com.tf.http.Requests;", [("Requests", "Requests", "com.tf.http")]),
    ("import com.tf.http.Clients as C", [("C", "Clients", "com.tf.http")]),
    ("use App\\Http\\ClientFactory;", [("ClientFactory", "ClientFactory", "App\\Http")]),
    ("use crate::http::client;", [("client", "client", "crate::http")]),
    ("use crate::http::{client, retry as r};", [("client", "client", "crate::http"), ("r", "retry", "crate::http")]),
    ('hc "github.com/tf/svc/internal/httpclient"', [("hc", None, "github.com/tf/svc/internal/httpclient")]),
    ('"github.com/tf/booking/internal/partners"', [("partners", None, "github.com/tf/booking/internal/partners")]),
    ("using Booking.Http;", [("Http", "Http", "Booking")]),
])
def test_parse_import_any_syntax(statement, expected):
    assert parse_import(statement)[: len(expected)] == expected

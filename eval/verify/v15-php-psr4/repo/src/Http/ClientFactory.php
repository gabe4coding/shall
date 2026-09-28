<?php

namespace App\Http;

use GuzzleHttp\Client;

final class ClientFactory
{
    public static function partner(): Client
    {
        return new Client(['base_uri' => 'https://partner.example', 'timeout' => 2.0]);
    }
}

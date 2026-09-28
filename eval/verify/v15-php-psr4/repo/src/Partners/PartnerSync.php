<?php

namespace App\Partners;

use App\Http\ClientFactory;

final class PartnerSync
{
    public function push(array $slots): void
    {
        ClientFactory::partner()->put('/slots', ['json' => $slots]);
    }
}

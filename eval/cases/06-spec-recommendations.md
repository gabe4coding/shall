# Spec: Restaurant recommendations on the search results page

Author: search team · Status: in review

## Summary

We will show a "Recommended for you" carousel at the top of the search results page,
powered by an external recommendation vendor (RecoCloud).

## Design

The search frontend calls a new endpoint on search-api:

    GET /search/recommendations?guestId={id}&city={city}

search-api forwards the guest id, the last 20 reservations of the guest and the current
search filters to RecoCloud over HTTPS and returns the list of restaurant ids it gets back.
The endpoint returns every recommended restaurant in a single response.

RecoCloud authenticates us with an API key that the vendor emails to the team lead. We
will store it in the search-api configuration file.

For debugging during the launch we will log each request and response, including the
guest email, so that we can reproduce bad recommendations.

## Alternatives

We looked at building our own model with the data team. It would take two quarters, so
we prefer the vendor for now.

## Timeline

- Week 1-2: integration with RecoCloud
- Week 3: A/B test on 10% of traffic

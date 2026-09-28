import type { ReviewsApi } from "./api";
import type { Review } from "./types";

export class ReviewsWidget {
  constructor(private readonly api: ReviewsApi) {}

  async load(restaurantId: string): Promise<Review[]> {
    return this.api.getJson<Review[]>(`/restaurants/${restaurantId}/reviews`);
  }
}

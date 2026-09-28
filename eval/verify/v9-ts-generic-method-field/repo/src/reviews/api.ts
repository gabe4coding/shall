import axios, { AxiosInstance } from "axios";

export class ReviewsApi {
  private readonly http: AxiosInstance;

  constructor(baseURL: string) {
    this.http = axios.create({
      baseURL,
      timeout: 2000,
    });
  }

  async health(): Promise<boolean> {
    const res = await this.http.get("/health");
    return res.status === 200;
  }

  async list(): Promise<string[]> {
    const res = await this.http.get<string[]>("/reviews");
    return res.data;
  }

  async getJson<T>(
    path: string,
  ): Promise<T> {
    const res = await this.http.get<T>(path);
    return res.data;
  }
}

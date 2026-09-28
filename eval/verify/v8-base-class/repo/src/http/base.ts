import axios, { AxiosInstance } from "axios";

export abstract class BaseHttpClient {
  protected readonly http: AxiosInstance;

  protected constructor(baseURL: string) {
    this.http = axios.create({ baseURL, timeout: 2000 });
  }
}

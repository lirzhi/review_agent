import axios from "axios";
import { Message } from "element-ui";

const service = axios.create({
  baseURL: "/api",
  timeout: 120000,
});

service.interceptors.response.use(
  (res) => {
    const payload = res.data || {};
    if (payload.code && payload.code !== 200) {
      Message.error(payload.message || "请求失败");
      return Promise.reject(new Error(payload.message || "request failed"));
    }
    return payload;
  },
  (err) => {
    Message.error(err.message || "网络错误");
    return Promise.reject(err);
  }
);

export default service;

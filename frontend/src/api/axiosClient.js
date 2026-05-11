import axios from "axios";

const axiosClient = axios.create({
  baseURL: "http://192.168.1.94:3000",
  headers: {
    "Content-Type": "application/json",
  },
});

export default axiosClient;
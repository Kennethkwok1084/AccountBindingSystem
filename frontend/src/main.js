import { createApp } from "vue";
import App from "./App.vue";
import router from "./router";
import Antd from "ant-design-vue";
import "ant-design-vue/dist/reset.css";
import "./styles.css";

const app = createApp(App);

app.config.errorHandler = (error, _instance, info) => {
	window.dispatchEvent(
		new CustomEvent("abs-runtime-error", {
			detail: {
				message: error?.message || "前端运行异常",
				code: "VUE_RUNTIME_ERROR",
				info,
			},
		}),
	);
	console.error(error);
};

app.use(router).use(Antd).mount("#app");

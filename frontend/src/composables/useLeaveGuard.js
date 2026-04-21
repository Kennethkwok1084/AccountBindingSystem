import { onBeforeUnmount, watch } from "vue";
import { onBeforeRouteLeave } from "vue-router";

export function useLeaveGuard(isDirty, message = "当前页面有未保存内容，确定离开吗？") {
  const handler = (event) => {
    if (!isDirty.value) {
      return;
    }
    event.preventDefault();
    event.returnValue = message;
  };

  watch(
    isDirty,
    (dirty) => {
      if (dirty) {
        window.addEventListener("beforeunload", handler);
      } else {
        window.removeEventListener("beforeunload", handler);
      }
    },
    { immediate: true },
  );

  onBeforeRouteLeave(() => {
    if (!isDirty.value) {
      return true;
    }
    return window.confirm(message);
  });

  onBeforeUnmount(() => {
    window.removeEventListener("beforeunload", handler);
  });
}

<template>
  <div class="frame">
    <AppSidebar />
    <div class="main">
      <AppHeader />
      <section class="content">
        <router-view />
      </section>
    </div>
  </div>
</template>

<script>
import AppHeader from "@/components/layout/AppHeader.vue";
import AppSidebar from "@/components/layout/AppSidebar.vue";

export default {
  name: "MainLayout",
  components: { AppHeader, AppSidebar },
};
</script>

<style scoped>
.frame {
  height: 100%;
  display: flex;
}

.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.content {
  flex: 1;
  padding: 18px;
  overflow: auto;
}
</style>

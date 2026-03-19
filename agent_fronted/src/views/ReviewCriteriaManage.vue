<template>
  <KnowledgeManage :classification="'\u5ba1\u8bc4\u89c4\u5219'" :display-name-prop="'\u5ba1\u8bc4\u51c6\u5219'" />
</template>

<script>
import KnowledgeManage from "./KnowledgeManage.vue";

export default {
  name: "ReviewCriteriaManage",
  components: { KnowledgeManage },
};
</script>

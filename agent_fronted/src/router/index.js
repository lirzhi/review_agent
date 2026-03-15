import Vue from "vue";
import Router from "vue-router";

import MainLayout from "@/layout/MainLayout.vue";
import Dashboard from "@/views/Dashboard.vue";
import KnowledgeManage from "@/views/KnowledgeManage.vue";
import PreReviewManage from "@/views/PreReviewManage.vue";
import PreReviewSession from "@/views/PreReviewSession.vue";

Vue.use(Router);

const CATEGORIES = [
  { slug: "guideline", title: "\u6307\u5bfc\u539f\u5219", classification: "\u6307\u5bfc\u539f\u5219" },
  { slug: "policy", title: "\u5236\u5ea6\u89c4\u8303", classification: "\u5236\u5ea6\u89c4\u8303" },
  { slug: "law", title: "\u6cd5\u5f8b\u6cd5\u89c4", classification: "\u6cd5\u5f8b\u6cd5\u89c4" },
  { slug: "pharmacopeia", title: "\u836f\u5178\u6570\u636e", classification: "\u836f\u5178\u6570\u636e" },
  { slug: "experience", title: "\u5386\u53f2\u7ecf\u9a8c", classification: "\u5386\u53f2\u7ecf\u9a8c" },
  { slug: "common-issue", title: "\u5171\u6027\u95ee\u9898", classification: "\u5171\u6027\u95ee\u9898" },
  { slug: "review-rule", title: "\u5ba1\u8bc4\u89c4\u5219", classification: "\u5ba1\u8bc4\u89c4\u5219" },
];

const knowledgeRoutes = CATEGORIES.map((c) => ({
  path: `knowledge/${c.slug}`,
  name: `knowledge-${c.slug}`,
  component: KnowledgeManage,
  meta: {
    title: `\u77e5\u8bc6\u5e93\u7ba1\u7406 - ${c.title}`,
    classification: c.classification,
  },
}));

export default new Router({
  mode: "hash",
  routes: [
    {
      path: "/",
      component: MainLayout,
      redirect: "/dashboard",
      children: [
        {
          path: "dashboard",
          name: "dashboard",
          component: Dashboard,
          meta: { title: "\u4eea\u8868\u76d8" },
        },
        {
          path: "knowledge",
          redirect: "/knowledge/guideline",
        },
        ...knowledgeRoutes,
        {
          path: "pre-review",
          name: "pre-review",
          component: PreReviewManage,
          meta: { title: "\u9884\u5ba1\u9879\u76ee\u7ba1\u7406" },
        },
        {
          path: "pre-review/session/:projectId",
          name: "pre-review-session",
          component: PreReviewSession,
          meta: { title: "\u9884\u5ba1\u4f1a\u8bdd" },
        },
      ],
    },
  ],
});


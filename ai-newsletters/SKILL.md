---
name: ai-newsletters
description: Fetch and summarize the latest AI news, research, and developments. This skill should be used when users want to stay updated on AI advancements, industry trends, new models, research papers, open source projects, or AI company announcements.
---

# AI Newsletters Skill

This skill provides comprehensive daily AI updates covering both news and technical developments — nothing important should be missed.

## Purpose

Fetch, curate, and summarize the latest developments in artificial intelligence including:
- New AI models and releases (GPT, Claude, Gemini, LLaMA, etc.)
- Research papers and breakthroughs (arXiv, top conferences)
- AI company announcements and industry news
- Open source projects, GitHub releases, and tooling
- Engineering blogs from frontier labs and practitioners
- Benchmark updates and model evaluations
- Policy and regulation changes
- Community hot topics: viral posts, debates, X threads, personal blogs

## When to Use

Activate this skill when users request:
- Daily or weekly AI news/updates
- Latest AI research or technical developments
- Information about new AI models or tools
- Open source AI projects and releases
- AI industry trends and analysis
- Specific AI company news
- AI policy or regulation updates

---

## Workflow

### 1. Determine Scope

Parse user request for:
- **Time range**: today, this week, this month (default: today)
- **Topics**: research, models, tools, open-source, policy, industry, community (default: ALL)
- **Sources**: specific sources or general (default: general)
- **Format**: brief summary, detailed analysis, bullet points (default: structured summary)
- **Language**: 默认使用**中文**输出所有内容（标题、摘要、分析、洞察）。如用户明确要求英文，则切换为英文。

### 2. Search Strategy

**强制执行规则（MANDATORY EXECUTION RULES）**：
- 必须执行下方全部 7 个搜索组（A/B/C/D/E/G/F），**一个都不能跳过**
- 每组内的每条查询都必须执行，不得以"代表性抽样"为由缩减
- 所有组必须**并行执行**（同一条消息中同时发起），不得串行依次执行
- 执行前先列出本次将执行的全部查询清单，执行后逐组确认已覆盖
- 若某组搜索结果为空，需明确在输出中注明"本组无符合条件内容"，而非静默跳过

**Always use exact dates** in queries to avoid mixing in older content. Run ALL search groups below in parallel — every group is mandatory for a complete picture.

#### Group A — News & Industry
- `"AI news [Month Day Year]"` e.g. `"AI news March 1 2026"`
- `"AI model release announcement [Month Day Year]"`
- `"AI company news [Month Day Year]"`
- `"AI startup funding [Month Year]"`

#### Group B — Technical: Papers & Research

**通用 AI 论文**
- `"arXiv AI papers [Month Day Year]"`
- `"AI research paper [Month Day Year] site:arxiv.org"`
- `"[Month Year] AI benchmark results"`
- `"LLM evaluation [Month Year] site:arxiv.org OR site:paperswithcode.com"`

**软件工程 × AI（SE + AI）定向检索**
- `"software engineering AI LLM arxiv [Year]"`
- `"code generation large language model software engineering site:arxiv.org [Year]"`
- `"LLM agent software development benchmark arxiv [Year]"`
- `"agentic coding SWE-bench arxiv [Month Year]"`
- `"AI coding agent context engineering arxiv [Year]"`

**软件测试 × AI（Testing + AI）定向检索**
- `"automated software testing LLM arxiv [Year]"`
- `"automated test generation AI LLM site:arxiv.org [Year]"`
- `"LLM automated program repair bug fixing arxiv [Year]"`
- `"structural testing LLM agent arxiv [Year]"`
- `"AI test oracle fuzzing mutation testing arxiv [Month Year]"`

**SE+AI 重点关注 benchmark（每次执行需检查是否有新 SOTA）**
- SWE-bench Verified — 真实 GitHub Issue 修复能力
- LiveCodeBench — 多语言代码生成（持续更新、无污染）
- E2EDevBench — 端到端软件开发场景
- Agent-Diff — 真实企业 API 任务（Slack/Box/Linear）
- Terminal-Bench Hard — DevOps / 系统级编程

#### Group C — Technical: Open Source & Engineering
- `"AI open source release [Month Day Year]"`
- `"GitHub AI trending [Month Year]"`
- `"AI engineering blog [Month Day Year] site:huggingface.co OR site:ai.meta.com OR site:research.google"`
- `"[Month Year] AI tools developer release site:github.com"`

#### Group D — Engineering & Practitioner Blogs
- `"[Month Day Year] site:simonwillison.net OR site:karpathy.ai OR site:interconnects.ai OR site:sebastianraschka.com"`
- `"AI technical deep dive [Month Day Year]"`
- `"Hugging Face blog [Month Year]"`
- `"[Month Year] AI engineering post site:huggingface.co/blog"`

#### Group E — Community Hot Topics
- `"AI Twitter X viral post thread [Month Day Year]"`
- `"AI community debate controversy [Month Day Year]"`
- `"AI viral blog post [Month Year]"`

#### Group G — Viral Products & New Launches
- `"Product Hunt AI [Month Day Year]"` — 当日/当周 AI 产品榜单
- `"AI app trending App Store [Month Year]"`
- `"AI demo viral X Twitter [Month Day Year]"` — X 上爆款 Demo 视频/截图
- `"new AI product launch [Month Day Year]"`
- `"AI tool just launched [Month Day Year] site:producthunt.com"`

#### Group F — Company Official Blogs
- `"OpenAI blog [Month Day Year] site:openai.com"`
- `"Anthropic blog [Month Day Year] site:anthropic.com"`
- `"Google DeepMind blog [Month Day Year] site:deepmind.google"`
- `"Meta AI blog [Month Day Year] site:ai.meta.com"`

### 3. Content Curation

Filter and organize findings:
- Prioritize authoritative sources (papers, official announcements, reputable tech news, engineering blogs)
- **Verify dates strictly**: each item must fall within the requested time range; discard anything older
- Remove duplicates and redundant information
- Categorize by topic area
- Identify significance and impact

**Recency check — discard if:**
- Product/paper/tool news older than 7 days (for "this week" requests)
- Breaking news older than 24 hours (for "today" requests)
- Evergreen topics with no specific new development this period (e.g. "MCP is popular" — skip unless a specific new release/event happened)

**Technical content — include if:**
- A new paper dropped on arXiv with notable results or novel method
- A new open-source repo/tool was released or hit a milestone (stars, v1.0, etc.)
- An engineering blog published a technical deep-dive or experiment this period
- A benchmark leaderboard had a meaningful update or upset

**Viral products & new launches — include if:**
- Ranked in Product Hunt AI top 5 on that day/week, with verifiable upvotes or comments
- An AI app demo video/screenshot went viral on X with high engagement (reposts, replies) — requires concrete post, not just "people are talking about it"
- A newly launched AI product has a unique capability, novel interaction paradigm, or notable traction (App Store chart position, waitlist numbers, user count milestone)
- Discard: stealth launches with no public signal, marketing announcements without product access

**Community hot topics — include only if:**
- A specific post/thread/article went viral in the exact time range
- There is a concrete trigger (specific blog post, X thread, data, incident) — not general ongoing discussion
- The controversy or debate is new this period

### 4. Summarization Format

```markdown
# AI Update — [Date Range]

## 🔥 Community Hot Topics
- **[Post/thread/incident title]**: What triggered it, why it spread, key reactions
  Source: [direct URL] | Date: [exact date]

## 🚀 Major Model Releases
- **[Model Name]**: Key capabilities, benchmarks, availability
  Source: [direct URL] | Date: [exact date]

## 🏢 Company Blogs & Official Announcements
- **[Company — post title]**: Key points
  Source: [direct URL] | Date: [exact date]

## 🔥 Viral Products & New Launches
- **[Product Name]** ([platform: Product Hunt / App Store / X demo]): What it does, what makes it stand out, traction signal (upvotes / chart position / engagement)
  Source: [direct URL] | Date: [exact date]

## 📄 Research & Papers
- **[Paper Title]** ([authors/lab]): Core contribution, key results, why it matters
  Source: [arxiv.org/abs/XXXX.XXXXX] | Date: [exact date]

## 🛠️ Open Source & Tooling
- **[Project/Tool Name]** ([GitHub or release link]): What it does, why notable (stars, use case, who released it)
  Source: [direct URL] | Date: [exact date]

## ⚙️ Engineering & Practitioner Blogs
- **[Post Title]** ([author/blog]): Key technical insight or finding
  Source: [direct URL] | Date: [exact date]

## 📜 Policy & Regulation
- **[Policy/Regulation/Event]**: Impact and implications
  Source: [direct URL] | Date: [exact date]

## 💡 Key Insights
- [Concrete new signal observed THIS period only — no evergreen observations]

---
*Generated on [Date] | Sources: [list of domains]*
```

**Omit any section with no qualifying content for the period — do not pad with old or generic items.**

### 5. Source Attribution

Always include **direct links to original articles**, not search proxy URLs.

**URL quality check — reject if the link:**
- Contains `vertexaisearch.cloud.google.com` (Google search proxy)
- Contains `grounding-api-redirect` (redirect wrapper)
- Is a bare domain root with no article path (e.g. `techcrunch.com` alone)

**To get real URLs, run follow-up searches:**
- `"[article title or key phrase]" site:[domain].com`
- `[paper title] site:arxiv.org`
- `[tool name] site:github.com`

For arXiv papers always link to the abstract page: `https://arxiv.org/abs/XXXX.XXXXX`

---

## Best Practices

1. **Completeness**: Run all 6 search groups every time — skipping technical groups is the main cause of missed important content
2. **Recency**: Use exact dates; verify every item falls within the requested time range
3. **Depth on technical items**: For papers, include the core method and result, not just the title; for open source, include what problem it solves
4. **Real URLs**: Always resolve proxy links to direct article/paper/repo URLs
5. **No padding**: Omit sections that have nothing qualifying — better to have 4 solid sections than 7 with filler
6. **Community signal**: Viral posts and practitioner blogs often surface important technical work before mainstream news does — treat them as primary signals, not afterthoughts
7. **Neutrality**: Present facts objectively; flag when claims are unverified or sourced from a single outlet

---

## Reference Sources

### News & Industry
- The Verge, TechCrunch, Ars Technica, MIT Technology Review, Wired
- VentureBeat AI, The Information, Bloomberg Tech, Reuters Tech

### Company Official Blogs
- openai.com/blog, anthropic.com/news, deepmind.google/discover/blog
- ai.meta.com/blog, research.google/blog, huggingface.co/blog
- mistral.ai/news, stability.ai/news

### Research & Papers
- arxiv.org (cs.AI, cs.LG, cs.CL, cs.CV, stat.ML)
- paperswithcode.com, semanticscholar.org
- Nature Machine Intelligence, JMLR, NeurIPS/ICML/ICLR proceedings

### Open Source & Tooling
- github.com/trending (filter: Python, language: AI/ML)
- huggingface.co/models (sort by recent)
- Papers with Code (trending repos)

### Viral Products & New Launches
- producthunt.com (daily AI top products, sort by upvotes)
- App Store / Google Play (top charts, AI category)
- X/Twitter: search `AI demo` sorted by latest + engagement
- theresanaiforthat.com (new AI tools directory)
- futuretools.io, toolify.ai (AI product aggregators)

### Practitioner & Engineering Blogs
- simonwillison.net, karpathy.ai, interconnects.ai
- sebastianraschka.com, eugeneyan.com, lilianweng.github.io
- newsletter.pragmaticengineer.com (AI sections)

### Community
- X/Twitter (AI researchers: @karpathy, @ylecun, @sama, @darioamodei, @goodfellow_ian)
- Reddit: r/MachineLearning, r/LocalLLaMA, r/artificial
- Hacker News (hn.algolia.com — filter by AI)

---

## Example Usage Patterns

**User**: "What's new in AI today?" / "今天 AI 有什么动态？"
→ Run all 6 search groups for today's date, return full structured summary

**User**: "This week's AI updates" / "本周 AI 进展"
→ Use date range queries across all groups for the past 7 days

**User**: "Latest AI papers" / "最新论文"
→ Focus Groups B + D, include paper abstracts and key results

**User**: "New open source AI tools" / "最新开源工具"
→ Focus Group C, include GitHub links, star counts, use cases

**User**: "OpenAI news" / "Anthropic 动态"
→ Focus Group F for that company + cross-reference Group A

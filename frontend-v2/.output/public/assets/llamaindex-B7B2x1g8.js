import{j as e}from"./main-BEToz-TC.js";import{u as t}from"./use-docs-content-ogu5VP42.js";function l(r){const n={a:"a",code:"code",h3:"h3",h4:"h4",li:"li",p:"p",pre:"pre",strong:"strong",table:"table",tbody:"tbody",td:"td",th:"th",thead:"thead",tr:"tr",ul:"ul",...t(),...r.components};return e.jsxs(e.Fragment,{children:[e.jsxs(n.p,{children:["The ",e.jsx(n.code,{children:"llama-index-tools-airweave"})," package provides an ",e.jsx(n.code,{children:"AirweaveToolSpec"})," that gives your LlamaIndex agents access to Airweave's semantic search capabilities."]}),`
`,e.jsx(n.h3,{children:"Prerequisites"}),`
`,e.jsx(n.p,{children:"Before you start you'll need:"}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"A collection with data"}),": at least one source connection must have completed its initial sync. See the ",e.jsx(n.a,{href:"https://docs.airweave.ai/quickstart",children:"Quickstart"})," if you need to set this up."]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"An API key"}),": Create one in the Airweave dashboard under ",e.jsx(n.strong,{children:"API Keys"}),"."]}),`
`]}),`
`,e.jsx(n.h3,{children:"Installation"}),`
`,e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`pip install llama-index llama-index-tools-airweave
`})}),`
`,e.jsx(n.h3,{children:"Quick Start"}),`
`,e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`import os
import asyncio
from llama_index.tools.airweave import AirweaveToolSpec
from llama_index.core.agent.workflow import FunctionAgent
from llama_index.llms.openai import OpenAI

# Initialize the Airweave tool
airweave_tool = AirweaveToolSpec(
    api_key=os.environ["AIRWEAVE_API_KEY"],
)

# Create an agent with the Airweave tools
agent = FunctionAgent(
    tools=airweave_tool.to_tool_list(),
    llm=OpenAI(model="gpt-4o-mini"),
    system_prompt="""You are a helpful assistant that can search through
    Airweave collections to answer questions about your organization's data.""",
)

# Use the agent to search your data
async def main():
    response = await agent.run(
        "Search the finance-data collection for Q4 revenue reports"
    )
    print(response)

if __name__ == "__main__":
    asyncio.run(main())
`})}),`
`,e.jsx(n.h3,{children:"Available Tools"}),`
`,e.jsxs(n.p,{children:["The ",e.jsx(n.code,{children:"AirweaveToolSpec"})," provides five tools that your agent can use:"]}),`
`,e.jsx(n.h4,{children:e.jsx(n.code,{children:"search_collection"})}),`
`,e.jsx(n.p,{children:"Simple search in a collection with default settings (most common use case)."}),`
`,e.jsxs(n.table,{children:[e.jsx(n.thead,{children:e.jsxs(n.tr,{children:[e.jsx(n.th,{children:"Parameter"}),e.jsx(n.th,{children:"Type"}),e.jsx(n.th,{children:"Description"})]})}),e.jsxs(n.tbody,{children:[e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"collection_id"})}),e.jsx(n.td,{children:"str"}),e.jsx(n.td,{children:"The readable ID of the collection"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"query"})}),e.jsx(n.td,{children:"str"}),e.jsx(n.td,{children:"Your search query"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"limit"})}),e.jsx(n.td,{children:"int"}),e.jsx(n.td,{children:"Max results to return (default: 10)"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"offset"})}),e.jsx(n.td,{children:"int"}),e.jsx(n.td,{children:"Pagination offset (default: 0)"})]})]})]}),`
`,e.jsx(n.h4,{children:e.jsx(n.code,{children:"advanced_search_collection"})}),`
`,e.jsx(n.p,{children:"Advanced search with full control over retrieval parameters."}),`
`,e.jsxs(n.table,{children:[e.jsx(n.thead,{children:e.jsxs(n.tr,{children:[e.jsx(n.th,{children:"Parameter"}),e.jsx(n.th,{children:"Type"}),e.jsx(n.th,{children:"Description"})]})}),e.jsxs(n.tbody,{children:[e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"collection_id"})}),e.jsx(n.td,{children:"str"}),e.jsx(n.td,{children:"The readable ID of the collection"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"query"})}),e.jsx(n.td,{children:"str"}),e.jsx(n.td,{children:"Your search query"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"limit"})}),e.jsx(n.td,{children:"int"}),e.jsx(n.td,{children:"Max results to return (default: 10)"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"offset"})}),e.jsx(n.td,{children:"int"}),e.jsx(n.td,{children:"Pagination offset (default: 0)"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"retrieval_strategy"})}),e.jsx(n.td,{children:"str"}),e.jsxs(n.td,{children:[e.jsx(n.code,{children:'"hybrid"'}),", ",e.jsx(n.code,{children:'"neural"'}),", or ",e.jsx(n.code,{children:'"keyword"'})]})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"temporal_relevance"})}),e.jsx(n.td,{children:"float"}),e.jsx(n.td,{children:"Weight recent content (0.0-1.0)"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"expand_query"})}),e.jsx(n.td,{children:"bool"}),e.jsx(n.td,{children:"Generate query variations"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"interpret_filters"})}),e.jsx(n.td,{children:"bool"}),e.jsx(n.td,{children:"Extract filters from natural language"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"rerank"})}),e.jsx(n.td,{children:"bool"}),e.jsx(n.td,{children:"Use LLM-based reranking"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"generate_answer"})}),e.jsx(n.td,{children:"bool"}),e.jsx(n.td,{children:"Generate natural language answer"})]})]})]}),`
`,e.jsxs(n.p,{children:["Returns a dictionary with ",e.jsx(n.code,{children:"documents"})," list and optional ",e.jsx(n.code,{children:"answer"})," field."]}),`
`,e.jsx(n.h4,{children:e.jsx(n.code,{children:"search_and_generate_answer"})}),`
`,e.jsx(n.p,{children:"Convenience method that searches and returns a direct natural language answer (RAG-style)."}),`
`,e.jsxs(n.table,{children:[e.jsx(n.thead,{children:e.jsxs(n.tr,{children:[e.jsx(n.th,{children:"Parameter"}),e.jsx(n.th,{children:"Type"}),e.jsx(n.th,{children:"Description"})]})}),e.jsxs(n.tbody,{children:[e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"collection_id"})}),e.jsx(n.td,{children:"str"}),e.jsx(n.td,{children:"The readable ID of the collection"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"query"})}),e.jsx(n.td,{children:"str"}),e.jsx(n.td,{children:"Your question in natural language"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"limit"})}),e.jsx(n.td,{children:"int"}),e.jsx(n.td,{children:"Max results to consider (default: 10)"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"use_reranking"})}),e.jsx(n.td,{children:"bool"}),e.jsx(n.td,{children:"Use reranking (default: True)"})]})]})]}),`
`,e.jsx(n.h4,{children:e.jsx(n.code,{children:"list_collections"})}),`
`,e.jsx(n.p,{children:"List all collections in your organization."}),`
`,e.jsxs(n.table,{children:[e.jsx(n.thead,{children:e.jsxs(n.tr,{children:[e.jsx(n.th,{children:"Parameter"}),e.jsx(n.th,{children:"Type"}),e.jsx(n.th,{children:"Description"})]})}),e.jsxs(n.tbody,{children:[e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"skip"})}),e.jsx(n.td,{children:"int"}),e.jsx(n.td,{children:"Pagination skip (default: 0)"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"limit"})}),e.jsx(n.td,{children:"int"}),e.jsx(n.td,{children:"Max collections to return (default: 100)"})]})]})]}),`
`,e.jsx(n.h4,{children:e.jsx(n.code,{children:"get_collection_info"})}),`
`,e.jsx(n.p,{children:"Get detailed information about a specific collection."}),`
`,e.jsxs(n.table,{children:[e.jsx(n.thead,{children:e.jsxs(n.tr,{children:[e.jsx(n.th,{children:"Parameter"}),e.jsx(n.th,{children:"Type"}),e.jsx(n.th,{children:"Description"})]})}),e.jsx(n.tbody,{children:e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"collection_id"})}),e.jsx(n.td,{children:"str"}),e.jsx(n.td,{children:"The readable ID of the collection"})]})})]}),`
`,e.jsx(n.h3,{children:"Advanced Examples"}),`
`,e.jsx(n.h4,{children:"Direct Tool Usage"}),`
`,e.jsx(n.p,{children:"You can use the tools directly without an agent:"}),`
`,e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`from llama_index.tools.airweave import AirweaveToolSpec

airweave_tool = AirweaveToolSpec(api_key="your-key")

# List collections
collections = airweave_tool.list_collections()
print(f"Found {len(collections)} collections")

# Simple search
results = airweave_tool.search_collection(
    collection_id="finance-data",
    query="Q4 revenue reports",
    limit=5
)

for doc in results:
    print(f"Score: {doc.metadata.get('score', 'N/A')}")
    print(f"Text: {doc.text[:200]}...")
`})}),`
`,e.jsx(n.h4,{children:"Advanced Search with All Options"}),`
`,e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`result = airweave_tool.advanced_search_collection(
    collection_id="finance-data",
    query="Q4 revenue reports",
    limit=20,
    retrieval_strategy="hybrid",
    temporal_relevance=0.3,
    expand_query=True,
    interpret_filters=True,
    rerank=True,
    generate_answer=True,
)

documents = result["documents"]
if "answer" in result:
    print(f"Generated Answer: {result['answer']}")
`})}),`
`,e.jsx(n.h4,{children:"RAG-Style Direct Answers"}),`
`,e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`answer = airweave_tool.search_and_generate_answer(
    collection_id="finance-data",
    query="What was our Q4 revenue growth?",
    limit=10,
    use_reranking=True,
)
print(answer)  # "Q4 revenue grew by 23% to $45M compared to Q3..."
`})}),`
`,e.jsx(n.h4,{children:"Using Different Retrieval Strategies"}),`
`,e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`# Keyword search for exact term matching
results = airweave_tool.advanced_search_collection(
    collection_id="legal-docs",
    query="GDPR compliance",
    retrieval_strategy="keyword",
)

# Neural search for semantic understanding
results = airweave_tool.advanced_search_collection(
    collection_id="research-papers",
    query="papers about transformer architectures",
    retrieval_strategy="neural",
)

# Hybrid search (default) - best of both worlds
results = airweave_tool.advanced_search_collection(
    collection_id="all-docs",
    query="machine learning best practices",
    retrieval_strategy="hybrid",
)
`})}),`
`,e.jsx(n.h4,{children:"Temporal Relevance"}),`
`,e.jsx(n.p,{children:"Weight recent documents higher in results:"}),`
`,e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`results = airweave_tool.advanced_search_collection(
    collection_id="news-articles",
    query="AI breakthroughs",
    temporal_relevance=0.8,  # 0.0 = no recency bias, 1.0 = only recent matters
)
`})}),`
`,e.jsx(n.h3,{children:"Custom Base URL"}),`
`,e.jsx(n.p,{children:"If you're self-hosting Airweave:"}),`
`,e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`airweave_tool = AirweaveToolSpec(
    api_key="your-api-key",
    base_url="https://your-airweave-instance.com",
)
`})}),`
`,e.jsx(n.h3,{children:"Using with Local Models"}),`
`,e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`pip install llama-index-llms-ollama
`})}),`
`,e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`from llama_index.llms.ollama import Ollama

agent = FunctionAgent(
    tools=airweave_tool.to_tool_list(),
    llm=Ollama(model="llama3.1", request_timeout=360.0),
)
`})}),`
`,e.jsx(n.h3,{children:"Learn More"}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsx(n.li,{children:e.jsx(n.a,{href:"https://docs.llamaindex.ai/",children:"LlamaIndex Documentation"})}),`
`,e.jsx(n.li,{children:e.jsx(n.a,{href:"https://llamahub.ai/l/tools/llama-index-tools-airweave?from=all",children:"LlamaIndex Airweave Tool on LlamaHub"})}),`
`,e.jsx(n.li,{children:e.jsx(n.a,{href:"https://github.com/airweave-ai/airweave",children:"Airweave GitHub"})}),`
`]})]})}function c(r={}){const{wrapper:n}={...t(),...r.components};return n?e.jsx(n,{...r,children:e.jsx(l,{...r})}):l(r)}export{c as default};

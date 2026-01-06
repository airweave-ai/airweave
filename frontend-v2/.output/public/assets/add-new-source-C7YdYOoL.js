import{j as e}from"./main-BEToz-TC.js";import{u as d}from"./use-docs-content-ogu5VP42.js";function l(n){const i={a:"a",code:"code",h2:"h2",h3:"h3",li:"li",ol:"ol",p:"p",pre:"pre",strong:"strong",ul:"ul",...d(),...n.components},{Card:o,CardGroup:s,CodeBlock:a,Step:t,Steps:c}=i;return o||r("Card"),s||r("CardGroup"),a||r("CodeBlock"),t||r("Step"),c||r("Steps"),e.jsxs(e.Fragment,{children:[e.jsx(i.p,{children:"Connectors are how Airweave pulls data from external systems, turns it into entities, and makes it searchable for agents. If your favorite tool or API is not yet supported, you can build a connector and either use it locally or contribute it back to the community."}),`
`,e.jsx(i.p,{children:"This guide will walk you through the full process step by step:"}),`
`,e.jsxs(i.ul,{children:[`
`,e.jsx(i.li,{children:"Setting up your environment and forking the repo"}),`
`,e.jsx(i.li,{children:"Defining authentication and configuration schemas"}),`
`,e.jsx(i.li,{children:"Creating entity definitions for your data"}),`
`,e.jsx(i.li,{children:"Implementing the source connector itself"}),`
`,e.jsx(i.li,{children:"Testing your connector inside the Airweave dashboard"}),`
`]}),`
`,e.jsx(i.p,{children:"Once complete, your connector will behave like any built-in integration. You can create collections, sync data, and query it through Airweave’s search APIs or MCP server."}),`
`,e.jsxs(i.p,{children:["If you plan to contribute your connector back to the project, please also review our ",e.jsx(i.a,{href:"https://github.com/airweave-ai/airweave/blob/main/CONTRIBUTING.md",children:"Contributing Guidelines"}),`
for details on branch naming, development workflow, and pull request process. For help at any point, you can join the `,e.jsx(i.a,{href:"https://discord.com/invite/484HY9Ehxt",children:"Airweave Discord"}),`
to connect with other contributors and maintainers.`]}),`
`,e.jsx(i.h2,{children:"How to add a Connector"}),`
`,e.jsxs(c,{children:[e.jsxs(t,{title:"Fork the repository",toc:!0,children:[e.jsxs(i.p,{children:["Get the ",e.jsx(i.a,{href:"https://github.com/airweave-ai/airweave/fork",children:"code"})," and set up your development environment."]}),e.jsx(i.pre,{children:e.jsx(i.code,{className:"language-bash",children:`git clone https://github.com/YOUR_USERNAME/airweave.git
cd airweave
./start.sh
`})})]}),e.jsxs(t,{title:"Create authentication schema",toc:!0,children:[e.jsxs(i.p,{children:["Define what credentials your source needs in ",e.jsx(i.a,{href:"https://github.com/airweave-ai/airweave/blob/main/backend/airweave/platform/configs/auth.py",children:e.jsx(i.code,{children:"backend/airweave/platform/configs/auth.py"})}),"."]}),e.jsx(i.pre,{children:e.jsx(i.code,{className:"language-python",children:`class GhibliAuthConfig(AuthConfig):
    """Studio Ghibli authentication credentials schema."""

    # No authentication needed for this public API
    pass
`})})]}),e.jsxs(t,{title:"Create source configuration",toc:!0,children:[e.jsxs(i.p,{children:["Define optional configuration options in ",e.jsx(i.a,{href:"https://github.com/airweave-ai/airweave/blob/main/backend/airweave/platform/configs/config.py",children:e.jsx(i.code,{children:"backend/airweave/platform/configs/config.py"})}),"."]}),e.jsx(i.pre,{children:e.jsx(i.code,{className:"language-python",children:`class GhibliConfig(SourceConfig):
    """Studio Ghibli configuration schema."""

    include_rt_scores: bool = Field(
        default=True,
        title="Include RT Scores",
        description="Whether to include Rotten Tomatoes scores in the metadata"
    )
`})})]}),e.jsxs(t,{title:"Define entity schemas",toc:!0,children:[e.jsxs(i.p,{children:["Create entity schemas in ",e.jsx(i.a,{href:"https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/entities",children:e.jsx(i.code,{children:"backend/airweave/platform/entities/your_source.py"})})," that define the structure of the data in the source."]}),e.jsx(i.pre,{children:e.jsx(i.code,{className:"language-python",children:`from datetime import datetime
from typing import List, Optional

from pydantic import Field

from airweave.platform.entities._base import ChunkEntity

class GhibliFilmEntity(ChunkEntity):
    """Schema for a Studio Ghibli film."""

    film_id: str = Field(..., description="Unique ID of the film")
    title: str = Field(..., description="Title of the film")
    original_title: str = Field(..., description="Original Japanese title")
    director: str = Field(..., description="Director of the film")
    producer: str = Field(..., description="Producer of the film")
    release_date: str = Field(..., description="Release date")
    running_time: str = Field(..., description="Running time in minutes")
    rt_score: Optional[str] = Field(None, description="Rotten Tomatoes score")
    people: List[str] = Field(default_factory=list, description="Characters in the film")
    species: List[str] = Field(default_factory=list, description="Species in the film")
    locations: List[str] = Field(default_factory=list, description="Locations in the film")
    vehicles: List[str] = Field(default_factory=list, description="Vehicles in the film")
`})}),e.jsx(i.p,{children:e.jsx(i.strong,{children:"Key points about entities:"})}),e.jsxs(i.ul,{children:[`
`,e.jsxs(i.li,{children:["Inherit from ",e.jsx(i.code,{children:"ChunkEntity"})," for searchable content (documents, posts, issues)"]}),`
`,e.jsxs(i.li,{children:["Inherit from ",e.jsx(i.code,{children:"FileEntity"})," for downloadable files (PDFs, images, attachments)"]}),`
`,e.jsxs(i.li,{children:["Use ",e.jsx(i.code,{children:"Field(...)"})," for required fields, ",e.jsx(i.code,{children:"Field(default=...)"})," for optional ones"]}),`
`,e.jsx(i.li,{children:"Add source-specific fields that are relevant for search and metadata"}),`
`]})]}),e.jsxs(t,{title:"Implement source",toc:!0,children:[e.jsxs(i.p,{children:["Create your source connector in ",e.jsx(i.a,{href:"https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources",children:e.jsx(i.code,{children:"backend/airweave/platform/sources/your_source.py"})}),"."]}),e.jsx(i.pre,{children:e.jsx(i.code,{className:"language-python",children:`from typing import AsyncGenerator, Optional, Dict, Any
import httpx

from airweave.platform.entities.ghibli import GhibliFilmEntity
from airweave.platform.decorators import source
from airweave.platform.sources._base import BaseSource
from airweave.platform.auth.schemas import AuthType

@source(
    name="Studio Ghibli",
    short_name="ghibli",
    auth_type=AuthType.none,
    auth_config_class="GhibliAuthConfig",
    config_class="GhibliConfig",
    labels=["Entertainment", "API"]
)
class GhibliSource(BaseSource):
    """Studio Ghibli source implementation."""

    @classmethod
    async def create(
        cls,
        credentials=None,
        config: Optional[Dict[str, Any]] = None
    ) -> "GhibliSource":
        """Create a new Ghibli source instance."""
        instance = cls()
        instance.config = config or {}
        return instance

    async def generate_entities(self) -> AsyncGenerator[GhibliFilmEntity, None]:
        """Generate entities from the Ghibli API."""
        async with httpx.AsyncClient() as client:
            response = await client.get("https://ghibli.rest/films")
            response.raise_for_status()
            films = response.json()

            for film in films:
                yield GhibliFilmEntity(
                    entity_id=film["id"],
                    film_id=film["id"],
                    title=film["title"],
                    original_title=film["original_title"],
                    content=film["description"],  # Required by ChunkEntity
                    director=film["director"],
                    producer=film["producer"],
                    release_date=film["release_date"],
                    running_time=film["running_time"],
                    rt_score=film["rt_score"] if self.config.get("include_rt_scores", True) else None,
                    people=film.get("people", []),
                    species=film.get("species", []),
                    locations=film.get("locations", []),
                    vehicles=film.get("vehicles", [])
                )
`})}),e.jsx(i.p,{children:e.jsx(i.strong,{children:"Key implementation points:"})}),e.jsxs(i.ul,{children:[`
`,e.jsx(i.li,{children:"Import your custom entity classes"}),`
`,e.jsxs(i.li,{children:["Use the ",e.jsx(i.code,{children:"@source()"})," decorator with your auth and config classes"]}),`
`,e.jsxs(i.li,{children:["Implement ",e.jsx(i.code,{children:"create()"})," classmethod that handles credentials and config"]}),`
`,e.jsxs(i.li,{children:["Implement ",e.jsx(i.code,{children:"generate_entities()"})," that yields your custom entity objects"]}),`
`,e.jsx(i.li,{children:"Handle authentication based on your auth type"}),`
`,e.jsx(i.li,{children:"Use config options to customize behavior"}),`
`]})]}),e.jsxs(t,{title:"Test your source",toc:!0,children:[e.jsx(i.p,{children:"Verify everything works by running Airweave and creating a test connection."}),e.jsxs(i.ol,{children:[`
`,e.jsxs(i.li,{children:[e.jsx(i.strong,{children:"Start Airweave"}),": Your connector appears automatically in the dashboard"]}),`
`,e.jsxs(i.li,{children:[e.jsx(i.strong,{children:"Create a collection"})," and add your new source"]}),`
`,e.jsxs(i.li,{children:[e.jsx(i.strong,{children:"Test the connection"})," and verify data syncs correctly"]}),`
`,e.jsxs(i.li,{children:[e.jsx(i.strong,{children:"Search your data"})," to confirm everything works end-to-end"]}),`
`]})]})]}),`
`,e.jsx(i.h3,{children:"File Structure"}),`
`,e.jsx(i.p,{children:"Your complete implementation will create files in these locations:"}),`
`,e.jsx(a,{title:"File structure",children:e.jsx(i.pre,{children:e.jsx(i.code,{children:`backend/airweave/platform/
├── configs/
│   ├── auth.py              # Add YourSourceAuthConfig class
│   └── config.py            # Add YourSourceConfig class
├── entities/
│   └── your_source.py       # Define entity schemas for your data
└── sources/
    └── your_source.py       # Your source implementation
`})})}),`
`,e.jsx(i.h3,{children:"Notes"}),`
`,e.jsxs(i.p,{children:["Be careful about what kind of authentication your app uses. Airweave supports many auth types including API keys, various OAuth2 flows, and database connections. Check your data source's API documentation to determine the correct ",e.jsx(i.code,{children:"AuthType"})," to use in your ",e.jsx(i.code,{children:"@source()"})," decorator."]}),`
`,e.jsxs(i.p,{children:["For OAuth2 sources, you'll also need to add your integration to the ",e.jsx(i.a,{href:"https://github.com/airweave-ai/airweave/blob/main/backend/airweave/platform/auth/yaml/dev.integrations.yaml",children:e.jsx(i.code,{children:"dev.integrations.yaml"})})," file."]}),`
`,e.jsx(i.h3,{children:"Contributing"}),`
`,e.jsxs(s,{cols:2,children:[e.jsx(o,{title:"Contribution Guidelines",icon:"fa-solid fa-code-pull-request",href:"https://github.com/airweave-ai/airweave/blob/main/CONTRIBUTING.md",children:e.jsx(i.p,{children:"Follow our guidelines for contributing new connectors"})}),e.jsx(o,{title:"Get Help",icon:"fa-brands fa-discord",href:"https://discord.gg/484HY9Ehxt",children:e.jsx(i.p,{children:"Join our Discord for help building your connector"})})]})]})}function p(n={}){const{wrapper:i}={...d(),...n.components};return i?e.jsx(i,{...n,children:e.jsx(l,{...n})}):l(n)}function r(n,i){throw new Error("Expected component `"+n+"` to be defined: you likely forgot to import, pass, or provide it.")}export{p as default};

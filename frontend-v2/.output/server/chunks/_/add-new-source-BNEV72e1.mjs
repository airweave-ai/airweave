import { jsx, jsxs, Fragment } from "react/jsx-runtime";
import { u as useMDXComponents } from "./use-docs-content-CQG4H0bA.mjs";
import "@tanstack/react-query";
import "react";
import "./router-BGxBdlkD.mjs";
import "@tanstack/react-router";
import "@tanstack/react-query-persist-client";
import "@radix-ui/react-slot";
import "class-variance-authority";
import "clsx";
import "tailwind-merge";
import "@radix-ui/react-dialog";
import "@radix-ui/react-tooltip";
import "zustand";
import "zustand/middleware";
import "@radix-ui/react-avatar";
import "@radix-ui/react-dropdown-menu";
import "cmdk";
import "sonner";
import "idb-keyval";
function _createMdxContent(props) {
  const _components = {
    a: "a",
    code: "code",
    h2: "h2",
    h3: "h3",
    li: "li",
    ol: "ol",
    p: "p",
    pre: "pre",
    strong: "strong",
    ul: "ul",
    ...useMDXComponents(),
    ...props.components
  }, { Card, CardGroup, CodeBlock, Step, Steps } = _components;
  if (!Card) _missingMdxReference("Card");
  if (!CardGroup) _missingMdxReference("CardGroup");
  if (!CodeBlock) _missingMdxReference("CodeBlock");
  if (!Step) _missingMdxReference("Step");
  if (!Steps) _missingMdxReference("Steps");
  return jsxs(Fragment, {
    children: [jsx(_components.p, {
      children: "Connectors are how Airweave pulls data from external systems, turns it into entities, and makes it searchable for agents. If your favorite tool or API is not yet supported, you can build a connector and either use it locally or contribute it back to the community."
    }), "\n", jsx(_components.p, {
      children: "This guide will walk you through the full process step by step:"
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsx(_components.li, {
        children: "Setting up your environment and forking the repo"
      }), "\n", jsx(_components.li, {
        children: "Defining authentication and configuration schemas"
      }), "\n", jsx(_components.li, {
        children: "Creating entity definitions for your data"
      }), "\n", jsx(_components.li, {
        children: "Implementing the source connector itself"
      }), "\n", jsx(_components.li, {
        children: "Testing your connector inside the Airweave dashboard"
      }), "\n"]
    }), "\n", jsx(_components.p, {
      children: "Once complete, your connector will behave like any built-in integration. You can create collections, sync data, and query it through Airweave’s search APIs or MCP server."
    }), "\n", jsxs(_components.p, {
      children: ["If you plan to contribute your connector back to the project, please also review our ", jsx(_components.a, {
        href: "https://github.com/airweave-ai/airweave/blob/main/CONTRIBUTING.md",
        children: "Contributing Guidelines"
      }), "\nfor details on branch naming, development workflow, and pull request process. For help at any point, you can join the ", jsx(_components.a, {
        href: "https://discord.com/invite/484HY9Ehxt",
        children: "Airweave Discord"
      }), "\nto connect with other contributors and maintainers."]
    }), "\n", jsx(_components.h2, {
      children: "How to add a Connector"
    }), "\n", jsxs(Steps, {
      children: [jsxs(Step, {
        title: "Fork the repository",
        toc: true,
        children: [jsxs(_components.p, {
          children: ["Get the ", jsx(_components.a, {
            href: "https://github.com/airweave-ai/airweave/fork",
            children: "code"
          }), " and set up your development environment."]
        }), jsx(_components.pre, {
          children: jsx(_components.code, {
            className: "language-bash",
            children: "git clone https://github.com/YOUR_USERNAME/airweave.git\ncd airweave\n./start.sh\n"
          })
        })]
      }), jsxs(Step, {
        title: "Create authentication schema",
        toc: true,
        children: [jsxs(_components.p, {
          children: ["Define what credentials your source needs in ", jsx(_components.a, {
            href: "https://github.com/airweave-ai/airweave/blob/main/backend/airweave/platform/configs/auth.py",
            children: jsx(_components.code, {
              children: "backend/airweave/platform/configs/auth.py"
            })
          }), "."]
        }), jsx(_components.pre, {
          children: jsx(_components.code, {
            className: "language-python",
            children: 'class GhibliAuthConfig(AuthConfig):\n    """Studio Ghibli authentication credentials schema."""\n\n    # No authentication needed for this public API\n    pass\n'
          })
        })]
      }), jsxs(Step, {
        title: "Create source configuration",
        toc: true,
        children: [jsxs(_components.p, {
          children: ["Define optional configuration options in ", jsx(_components.a, {
            href: "https://github.com/airweave-ai/airweave/blob/main/backend/airweave/platform/configs/config.py",
            children: jsx(_components.code, {
              children: "backend/airweave/platform/configs/config.py"
            })
          }), "."]
        }), jsx(_components.pre, {
          children: jsx(_components.code, {
            className: "language-python",
            children: 'class GhibliConfig(SourceConfig):\n    """Studio Ghibli configuration schema."""\n\n    include_rt_scores: bool = Field(\n        default=True,\n        title="Include RT Scores",\n        description="Whether to include Rotten Tomatoes scores in the metadata"\n    )\n'
          })
        })]
      }), jsxs(Step, {
        title: "Define entity schemas",
        toc: true,
        children: [jsxs(_components.p, {
          children: ["Create entity schemas in ", jsx(_components.a, {
            href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/entities",
            children: jsx(_components.code, {
              children: "backend/airweave/platform/entities/your_source.py"
            })
          }), " that define the structure of the data in the source."]
        }), jsx(_components.pre, {
          children: jsx(_components.code, {
            className: "language-python",
            children: 'from datetime import datetime\nfrom typing import List, Optional\n\nfrom pydantic import Field\n\nfrom airweave.platform.entities._base import ChunkEntity\n\nclass GhibliFilmEntity(ChunkEntity):\n    """Schema for a Studio Ghibli film."""\n\n    film_id: str = Field(..., description="Unique ID of the film")\n    title: str = Field(..., description="Title of the film")\n    original_title: str = Field(..., description="Original Japanese title")\n    director: str = Field(..., description="Director of the film")\n    producer: str = Field(..., description="Producer of the film")\n    release_date: str = Field(..., description="Release date")\n    running_time: str = Field(..., description="Running time in minutes")\n    rt_score: Optional[str] = Field(None, description="Rotten Tomatoes score")\n    people: List[str] = Field(default_factory=list, description="Characters in the film")\n    species: List[str] = Field(default_factory=list, description="Species in the film")\n    locations: List[str] = Field(default_factory=list, description="Locations in the film")\n    vehicles: List[str] = Field(default_factory=list, description="Vehicles in the film")\n'
          })
        }), jsx(_components.p, {
          children: jsx(_components.strong, {
            children: "Key points about entities:"
          })
        }), jsxs(_components.ul, {
          children: ["\n", jsxs(_components.li, {
            children: ["Inherit from ", jsx(_components.code, {
              children: "ChunkEntity"
            }), " for searchable content (documents, posts, issues)"]
          }), "\n", jsxs(_components.li, {
            children: ["Inherit from ", jsx(_components.code, {
              children: "FileEntity"
            }), " for downloadable files (PDFs, images, attachments)"]
          }), "\n", jsxs(_components.li, {
            children: ["Use ", jsx(_components.code, {
              children: "Field(...)"
            }), " for required fields, ", jsx(_components.code, {
              children: "Field(default=...)"
            }), " for optional ones"]
          }), "\n", jsx(_components.li, {
            children: "Add source-specific fields that are relevant for search and metadata"
          }), "\n"]
        })]
      }), jsxs(Step, {
        title: "Implement source",
        toc: true,
        children: [jsxs(_components.p, {
          children: ["Create your source connector in ", jsx(_components.a, {
            href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources",
            children: jsx(_components.code, {
              children: "backend/airweave/platform/sources/your_source.py"
            })
          }), "."]
        }), jsx(_components.pre, {
          children: jsx(_components.code, {
            className: "language-python",
            children: 'from typing import AsyncGenerator, Optional, Dict, Any\nimport httpx\n\nfrom airweave.platform.entities.ghibli import GhibliFilmEntity\nfrom airweave.platform.decorators import source\nfrom airweave.platform.sources._base import BaseSource\nfrom airweave.platform.auth.schemas import AuthType\n\n@source(\n    name="Studio Ghibli",\n    short_name="ghibli",\n    auth_type=AuthType.none,\n    auth_config_class="GhibliAuthConfig",\n    config_class="GhibliConfig",\n    labels=["Entertainment", "API"]\n)\nclass GhibliSource(BaseSource):\n    """Studio Ghibli source implementation."""\n\n    @classmethod\n    async def create(\n        cls,\n        credentials=None,\n        config: Optional[Dict[str, Any]] = None\n    ) -> "GhibliSource":\n        """Create a new Ghibli source instance."""\n        instance = cls()\n        instance.config = config or {}\n        return instance\n\n    async def generate_entities(self) -> AsyncGenerator[GhibliFilmEntity, None]:\n        """Generate entities from the Ghibli API."""\n        async with httpx.AsyncClient() as client:\n            response = await client.get("https://ghibli.rest/films")\n            response.raise_for_status()\n            films = response.json()\n\n            for film in films:\n                yield GhibliFilmEntity(\n                    entity_id=film["id"],\n                    film_id=film["id"],\n                    title=film["title"],\n                    original_title=film["original_title"],\n                    content=film["description"],  # Required by ChunkEntity\n                    director=film["director"],\n                    producer=film["producer"],\n                    release_date=film["release_date"],\n                    running_time=film["running_time"],\n                    rt_score=film["rt_score"] if self.config.get("include_rt_scores", True) else None,\n                    people=film.get("people", []),\n                    species=film.get("species", []),\n                    locations=film.get("locations", []),\n                    vehicles=film.get("vehicles", [])\n                )\n'
          })
        }), jsx(_components.p, {
          children: jsx(_components.strong, {
            children: "Key implementation points:"
          })
        }), jsxs(_components.ul, {
          children: ["\n", jsx(_components.li, {
            children: "Import your custom entity classes"
          }), "\n", jsxs(_components.li, {
            children: ["Use the ", jsx(_components.code, {
              children: "@source()"
            }), " decorator with your auth and config classes"]
          }), "\n", jsxs(_components.li, {
            children: ["Implement ", jsx(_components.code, {
              children: "create()"
            }), " classmethod that handles credentials and config"]
          }), "\n", jsxs(_components.li, {
            children: ["Implement ", jsx(_components.code, {
              children: "generate_entities()"
            }), " that yields your custom entity objects"]
          }), "\n", jsx(_components.li, {
            children: "Handle authentication based on your auth type"
          }), "\n", jsx(_components.li, {
            children: "Use config options to customize behavior"
          }), "\n"]
        })]
      }), jsxs(Step, {
        title: "Test your source",
        toc: true,
        children: [jsx(_components.p, {
          children: "Verify everything works by running Airweave and creating a test connection."
        }), jsxs(_components.ol, {
          children: ["\n", jsxs(_components.li, {
            children: [jsx(_components.strong, {
              children: "Start Airweave"
            }), ": Your connector appears automatically in the dashboard"]
          }), "\n", jsxs(_components.li, {
            children: [jsx(_components.strong, {
              children: "Create a collection"
            }), " and add your new source"]
          }), "\n", jsxs(_components.li, {
            children: [jsx(_components.strong, {
              children: "Test the connection"
            }), " and verify data syncs correctly"]
          }), "\n", jsxs(_components.li, {
            children: [jsx(_components.strong, {
              children: "Search your data"
            }), " to confirm everything works end-to-end"]
          }), "\n"]
        })]
      })]
    }), "\n", jsx(_components.h3, {
      children: "File Structure"
    }), "\n", jsx(_components.p, {
      children: "Your complete implementation will create files in these locations:"
    }), "\n", jsx(CodeBlock, {
      title: "File structure",
      children: jsx(_components.pre, {
        children: jsx(_components.code, {
          children: "backend/airweave/platform/\n├── configs/\n│   ├── auth.py              # Add YourSourceAuthConfig class\n│   └── config.py            # Add YourSourceConfig class\n├── entities/\n│   └── your_source.py       # Define entity schemas for your data\n└── sources/\n    └── your_source.py       # Your source implementation\n"
        })
      })
    }), "\n", jsx(_components.h3, {
      children: "Notes"
    }), "\n", jsxs(_components.p, {
      children: ["Be careful about what kind of authentication your app uses. Airweave supports many auth types including API keys, various OAuth2 flows, and database connections. Check your data source's API documentation to determine the correct ", jsx(_components.code, {
        children: "AuthType"
      }), " to use in your ", jsx(_components.code, {
        children: "@source()"
      }), " decorator."]
    }), "\n", jsxs(_components.p, {
      children: ["For OAuth2 sources, you'll also need to add your integration to the ", jsx(_components.a, {
        href: "https://github.com/airweave-ai/airweave/blob/main/backend/airweave/platform/auth/yaml/dev.integrations.yaml",
        children: jsx(_components.code, {
          children: "dev.integrations.yaml"
        })
      }), " file."]
    }), "\n", jsx(_components.h3, {
      children: "Contributing"
    }), "\n", jsxs(CardGroup, {
      cols: 2,
      children: [jsx(Card, {
        title: "Contribution Guidelines",
        icon: "fa-solid fa-code-pull-request",
        href: "https://github.com/airweave-ai/airweave/blob/main/CONTRIBUTING.md",
        children: jsx(_components.p, {
          children: "Follow our guidelines for contributing new connectors"
        })
      }), jsx(Card, {
        title: "Get Help",
        icon: "fa-brands fa-discord",
        href: "https://discord.gg/484HY9Ehxt",
        children: jsx(_components.p, {
          children: "Join our Discord for help building your connector"
        })
      })]
    })]
  });
}
function MDXContent(props = {}) {
  const { wrapper: MDXLayout } = {
    ...useMDXComponents(),
    ...props.components
  };
  return MDXLayout ? jsx(MDXLayout, {
    ...props,
    children: jsx(_createMdxContent, {
      ...props
    })
  }) : _createMdxContent(props);
}
function _missingMdxReference(id, component) {
  throw new Error("Expected component `" + id + "` to be defined: you likely forgot to import, pass, or provide it.");
}
export {
  MDXContent as default
};

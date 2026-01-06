import{j as e}from"./main-BEToz-TC.js";import{u as s}from"./use-docs-content-ogu5VP42.js";function t(i){const n={code:"code",h2:"h2",li:"li",p:"p",pre:"pre",table:"table",tbody:"tbody",td:"td",th:"th",thead:"thead",tr:"tr",ul:"ul",...s(),...i.components};return e.jsxs(e.Fragment,{children:[e.jsx(n.p,{children:"API requests are rate-limited per organization based on your billing plan. Limits are enforced per minute using a sliding window."}),`
`,e.jsx(n.h2,{children:"Limits by Plan"}),`
`,e.jsxs(n.table,{children:[e.jsx(n.thead,{children:e.jsxs(n.tr,{children:[e.jsx(n.th,{children:"Plan"}),e.jsx(n.th,{children:"Requests per Minute"})]})}),e.jsxs(n.tbody,{children:[e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"Developer"}),e.jsx(n.td,{children:"10"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"Pro"}),e.jsx(n.td,{children:"100"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"Team"}),e.jsx(n.td,{children:"250"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"Enterprise"}),e.jsx(n.td,{children:"Unlimited"})]})]})]}),`
`,e.jsx(n.h2,{children:"Rate Limit Headers"}),`
`,e.jsx(n.p,{children:"All API responses include rate limit information:"}),`
`,e.jsx(n.pre,{children:e.jsx(n.code,{children:`RateLimit-Limit: 100
RateLimit-Remaining: 95
RateLimit-Reset: 1729012345
`})}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"RateLimit-Limit"}),": Maximum requests per minute"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"RateLimit-Remaining"}),": Requests left in current window"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"RateLimit-Reset"}),": Unix timestamp when limit resets"]}),`
`]}),`
`,e.jsx(n.h2,{children:"Rate Limit Exceeded"}),`
`,e.jsxs(n.p,{children:["When you exceed your limit, you'll receive a ",e.jsx(n.code,{children:"429 Too Many Requests"})," response with a ",e.jsx(n.code,{children:"Retry-After"})," header indicating seconds until you can retry."]}),`
`,e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-json",children:`{
  "detail": "Rate limit exceeded. Try again in 42 seconds."
}
`})})]})}function l(i={}){const{wrapper:n}={...s(),...i.components};return n?e.jsx(n,{...i,children:e.jsx(t,{...i})}):t(i)}export{l as default};

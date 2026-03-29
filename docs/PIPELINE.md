## The Pipeline Architecture:
```mermaid
graph TD
%% Agents and Tools %%
    A(User: Question & Files) -->|1. Submit Query| B(Planner Agent: GPT-OSS 20B)
    B -->|2. Generate sub-questions| C{Researcher: Tool Orchestrator}
    
%% Tool can be selected %%
    subgraph Tools
        C -.->|3a. Has PDFs?| D[PDF Reader]
        C -.->|3b. Historical Data| E[Tavily Web Search]
        C -.->|3c. Academic Paper| F[Exa/ArXiv Search]
    end
    
    D -->|4. Text Chunks| G(Data Accumulator)
    E -->|4. Web Pages| G
    F -->|4. Academic Findings| G
    
    G -->|5.1 Raw Sources| H(Analyst Agent: Qwen 3.5 32B)
    H -->|5.2 Low Confident| C
    
%% Verifier %%
    H -->|6. Key Findings & Confidence| I(Writer Agent: GPT-OSS 120B)
    I -->|7. Draft Report| J(Verifier Agent: GPT-OSS 120B)
    
%% Logic Verifier %%
    J -->|8a. No Hallucinations?| K[Publish Node]
    K -->|9. Final SSE Stream| L(User: Verified Report)
    
    J ==>|8b. Factual Error!| I
    
    classDef user fill:#E1F5FE,stroke:#01579B,stroke-width:2px;
    classDef agent fill:#E8F5E9,stroke:#1B5E20,stroke-width:2px,rx:10,ry:10;
    classDef tool fill:#FFF3E0,stroke:#E65100,stroke-width:2px,stroke-dasharray: 5,5;
    classDef process fill:#F3E5F5,stroke:#4A148C,stroke-width:1px;
    classDef error fill:#FFEBEE,stroke:#B71C1C,stroke-width:3px;
    
    class A,L user;
    class B,H,I,J,K agent;
    class D,E,F tool;
    class G process;
    class J error;
```

1.  **Planner (GPT-OSS 20B):** Decomposes complex queries into 3-5 targeted sub-questions.
2.  **Researcher (Tool Orchestrator):** Dynamically selects between **[Tavily Search](https://www.tavily.com/)**, **[ArXiv](https://arxiv.org/)**, and **[PDF Reader](https://pymupdf.io/)** based on query intent.
3.  **Analyst (Qwen 3.5 32B):** Evaluates source credibility, extracts key findings, and calculates an `overall_confidence` score.
4.  **Writer (GPT-OSS 120B):** Synthesizes a 500-700 word academic report with inline citations.
5.  **Verifier (GPT-OSS 120B):** Fact-checks the draft against raw sources. If errors are found, it triggers a **Revision Loop** back to the Writer.
6.  **Publisher:** Streams the final, verified report to the UI once quality is guaranteed.

// Shared prompt templates for Prompt Builder: used by the web app (index.html),
// the desktop app (promptgen_gui.py) and the command line (promptgen.py).
// Edit the templates here. Everything after the = sign must stay strict JSON
// (double quotes, no trailing commas, no comments), because Python reads it too.
// Detection patterns are tried in order against the lower-cased task text.
window.PROMPT_TEMPLATES = {
  "models": [
    "claude-opus-5-5",
    "claude-sonnet-5-5",
    "claude-haiku-5-5"
  ],
  "lengths": {
    "short": "Keep it brief: a few sentences or a short list.",
    "medium": "Moderate length: thorough but no padding.",
    "long": "Be comprehensive and detailed."
  },
  "default_labels": {
    "goal": "Goal: why you need this",
    "audience": "Audience: who it's for",
    "tone": "Tone (e.g. friendly, formal, blunt)",
    "format": "Output format (blank uses the type's default)",
    "role": "Role for the AI (blank uses the type's default)",
    "context": [
      "Background",
      "Anything the AI should know: facts, situation, constraints."
    ],
    "rules": [
      "Rules",
      "One per line, e.g. \"Under 150 words\"."
    ],
    "example": [
      "Example of what you want",
      "Optional. Used as a guide to style and structure."
    ]
  },
  "detect": [
    [
      "reverse-engineer",
      "\\b(reverse[- ]?engineer\\w*|deconstruct\\w*|break down how|figure out how|how (was|were|did|does|do) .{1,60} (made|built|created|work)|\"\n                             r\"what makes .{1,60} (work|successful|popular|so good|go viral))\\b"
    ],
    [
      "web-design",
      "\\b(web ?sites?|landing ?page|home ?page|web ?design|web ?page|web ?app ui|portfolio site|wireframe|hero section|pricing page|signup page|sign-up page)\\b"
    ],
    [
      "image",
      "\\b(image|picture|photo\\w*|illustration|logo|render|drawing|painting|wallpaper|watercolou?r|portrait|landscape|isometric|35mm|digital art|concept art|pixel art)\\b"
    ],
    [
      "code",
      "\\b(code|script|function|bug|api|program|python|javascript|sql|regex|refactor|debug)\\b"
    ],
    [
      "brainstorm",
      "\\b(ideas?|brainstorm|names?|suggest|options)\\b"
    ],
    [
      "analysis",
      "\\b(analy[sz]e|compare|evaluate|review|assess|explain why|pros and cons)\\b"
    ],
    [
      "writing",
      "\\b(write|email|essay|post|article|letter|summar|rewrite|copy|story|bio)\\b"
    ]
  ],
  "polish_system": "You improve prompts that will be given to an AI model. You receive a draft prompt built from a template and return a better version of it.\n\nMake the prompt clearer, more specific and more useful to the model that will receive it:\n- Keep every requirement the draft states; do not drop the user's audience, tone, length, rules or format.\n- Remove guidelines that are generic, redundant or contradict each other.\n- Where the task is vague, add the specifics a capable expert would want, without inventing facts about the user's situation.\n- Fix grammar and capitalisation, and turn terse fragments into clear instructions.\n- Keep the XML-tagged section structure if the draft has one, and keep any {{PLACEHOLDER}} text exactly as written.\n- If the draft is an image-generation prompt (one descriptive paragraph, maybe an \"Avoid:\" line), keep that form: a vivid, concrete description of subject, setting, lighting, composition and style, not instructions.\n\nReturn only the improved prompt, with no preamble, commentary or code fences.",
  "types": {
    "general": {
      "name": "General",
      "role": "a knowledgeable, careful assistant",
      "guidelines": [
        "If something important is ambiguous, state the assumption you made.",
        "Prefer concrete specifics over generic statements."
      ],
      "format": "Clear prose, using headings or lists only where they help."
    },
    "writing": {
      "name": "Writing",
      "role": "an experienced writer and editor",
      "guidelines": [
        "Write for the stated audience: match their vocabulary and what they already know.",
        "Lead with the most important point.",
        "Cut filler, clichés, and hedging that doesn't add meaning."
      ],
      "format": "Finished, ready-to-use text with no commentary before or after it."
    },
    "code": {
      "name": "Code",
      "role": "a senior software engineer",
      "guidelines": [
        "Write correct, idiomatic, readable code; handle realistic edge cases and errors.",
        "Do not invent APIs or libraries; say so if something is uncertain.",
        "Keep the solution as simple as the task allows."
      ],
      "format": "Code in fenced blocks with the language named, followed by a short explanation of key decisions and how to run or test it."
    },
    "analysis": {
      "name": "Analysis",
      "role": "a rigorous analyst",
      "guidelines": [
        "Separate facts from inferences, and say how confident you are in each conclusion.",
        "Consider alternative explanations before settling on one.",
        "Ground every claim in the provided material where possible."
      ],
      "format": "A one-paragraph summary of the conclusion first, then the supporting reasoning, then open questions or risks."
    },
    "brainstorm": {
      "name": "Brainstorm",
      "role": "a creative collaborator",
      "guidelines": [
        "Generate a wide range of ideas, including some unconventional ones.",
        "Avoid near-duplicates; each idea should be meaningfully different.",
        "Briefly note why each idea could work."
      ],
      "format": "A numbered list of ideas, each with a one-line rationale. Mark your top 3 picks at the end."
    },
    "web-design": {
      "name": "Web design",
      "role": "a senior web designer and front-end developer with a sharp eye for typography, layout and usability",
      "guidelines": [
        "Design around the site's single most important goal and make the primary call to action obvious.",
        "Build a clear visual hierarchy: one focal point per section, generous whitespace and a consistent spacing scale.",
        "Commit to a deliberate, distinctive visual direction (type pairing, colour palette with defined roles, imagery style); avoid generic template layouts.",
        "Write real, specific copy for the audience instead of placeholder text.",
        "Make it mobile-first and fully responsive at phone, tablet and desktop widths.",
        "Meet WCAG 2.2 AA: sufficient contrast, semantic HTML, keyboard navigation, visible focus states and alt text.",
        "Keep it fast: lightweight assets and no unnecessary libraries."
      ],
      "format": "First, a short design brief: the visual direction, the colour palette (hex values and what each is for), the typography, and the page sections in order. Then the complete page as one self-contained HTML file with embedded CSS (and minimal JavaScript only where needed) in a single fenced code block.",
      "tone_line": "Aim for a {tone} look and feel, in both the visuals and the copy.",
      "labels": {
        "goal": "Goal: what should visitors do (e.g. book a call)",
        "audience": "Audience: who visits the site",
        "tone": "Look and feel (e.g. clean and minimal, bold, playful)",
        "format": "Deliverable (blank = design brief + one HTML file)",
        "context": [
          "About the site",
          "The business or project, the pages or sections you need, brand colours, fonts, and sites you like the look of."
        ],
        "rules": [
          "Rules",
          "One per line, e.g. \"Use our brand blue #1E6FFF\" or \"No stock photos\"."
        ],
        "example": [
          "Example of what you want",
          "Optional. Paste copy, a layout sketch or a reference."
        ]
      }
    },
    "reverse-engineer": {
      "name": "Reverse engineer",
      "role": "an expert at reverse engineering how things are made and why they work",
      "guidelines": [
        "Start by pinning down exactly what the subject is and what makes it effective or distinctive.",
        "Break it into its components or building blocks; explain how each one works and how they fit together.",
        "Uncover the underlying principles, decisions and trade-offs its creator likely made.",
        "Clearly separate what is evident from the subject itself from what you are inferring.",
        "Call out the non-obvious details that make the biggest difference to the result.",
        "Turn the analysis into a practical blueprint someone could follow to create something similar of their own.",
        "Capture the principles and techniques rather than copying protected material word for word."
      ],
      "format": "Use these headings: 1) What it is and why it works (a short summary); 2) The breakdown (each component and its role); 3) Underlying principles and likely decisions; 4) Step-by-step blueprint to make your own; 5) Common pitfalls when replicating it.",
      "context_tag": "subject",
      "labels": {
        "goal": "Goal: what you want to make or learn from it",
        "audience": "Audience: who the breakdown is for (e.g. a beginner)",
        "format": "Output format (blank = breakdown + step-by-step blueprint)",
        "context": [
          "The thing to reverse engineer",
          "Paste it or describe it: an ad, a website, a product, a song structure, code, a recipe, a business model, a viral post…"
        ],
        "rules": [
          "Rules",
          "One per line, e.g. \"Focus on the pricing strategy\"."
        ]
      }
    },
    "image": {
      "name": "Image",
      "image": true,
      "hide": [
        "goal",
        "audience",
        "length",
        "role",
        "example",
        "input_slot"
      ],
      "labels": {
        "tone": "Mood (e.g. moody, cheerful, serene)",
        "format": "Style (e.g. watercolor, 35mm photo, isometric 3D)",
        "context": [
          "Subject details and setting",
          ""
        ],
        "rules": [
          "Things to avoid",
          "One per line, e.g. text, watermarks, blurry faces."
        ]
      }
    }
  }
};

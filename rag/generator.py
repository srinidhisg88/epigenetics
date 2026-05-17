"""
RAG Generator module for Epilepsy Diagnostic Assistant.

Handles LLM-based response generation using Groq API with retrieved context.
"""

import os
import re
from typing import List, Dict, Optional
from groq import Groq
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ── Post-processing: auto-highlight syndromes and seizure types ───────────────
SYNDROMES = [
    "Dravet Syndrome", "Dravet syndrome",
    "Tuberous Sclerosis Complex", "tuberous sclerosis complex",
    "Tuberous Sclerosis", "tuberous sclerosis",
    "West Syndrome", "West syndrome",
    "Ohtahara Syndrome", "Ohtahara syndrome",
    "Rett Syndrome", "Rett syndrome",
    "GLUT1 Deficiency Syndrome", "GLUT1 deficiency syndrome", "GLUT1 Deficiency",
    "Lennox-Gastaut Syndrome", "Lennox-Gastaut syndrome",
    "CDKL5 Deficiency Disorder",
    "Benign Familial Neonatal Epilepsy", "benign familial neonatal epilepsy",
    "KCNQ2 Encephalopathy", "KCNQ2 encephalopathy",
    "SCN8A Encephalopathy", "SCN8A encephalopathy",
    "STXBP1 Encephalopathy", "STXBP1 encephalopathy",
    "PCDH19 Epilepsy", "PCDH19 epilepsy",
    "Developmental Epileptic Encephalopathy", "developmental epileptic encephalopathy",
    "Epileptic Encephalopathy", "epileptic encephalopathy",
    "GEFS\+", "generalized epilepsy with febrile seizures plus",
    "Malignant Migrating Focal Seizures",
]

SYMPTOMS = [
    "tonic-clonic seizures", "tonic-clonic",
    "febrile seizures", "febrile seizure",
    "myoclonic seizures", "myoclonic jerks", "myoclonic",
    "absence seizures", "absence epilepsy",
    "focal seizures", "focal epilepsy",
    "infantile spasms",
    "epileptic spasms",
    "atonic seizures",
    "clonic seizures",
    "status epilepticus",
    "hypotonia",
    "developmental regression", "developmental delay",
    "intellectual disability",
    "cortical tubers",
    "non-cancerous tumors", "benign tumors",
    "neural excitability", "neuronal excitability",
    "loss-of-function", "loss of function",
    "gain-of-function", "gain of function",
]

def highlight_clinical_terms(text: str) -> str:
    """Wrap known syndromes and symptoms with HTML span tags for frontend highlighting."""
    # Syndromes → purple
    for term in SYNDROMES:
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        # Only wrap if not already wrapped
        text = pattern.sub(
            lambda m: m.group() if 'class="syndrome"' in text[max(0, text.find(m.group())-20):text.find(m.group())]
            else f'<span class="syndrome">{m.group()}</span>',
            text
        )
    # Symptoms → amber
    for term in SYMPTOMS:
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        text = pattern.sub(
            lambda m: m.group() if 'class="symptom"' in text[max(0, text.find(m.group())-20):text.find(m.group())]
            else f'<span class="symptom">{m.group()}</span>',
            text
        )
    return text


# System prompt for the clinical geneticist assistant
SYSTEM_PROMPT = """You are an expert clinical geneticist specializing in epilepsy genetics.
You assist clinicians in interpreting genetic variant pathogenicity and recommending appropriate management.

CRITICAL PRESENTATION RULES — READ CAREFULLY:
- NEVER mention "SHAP", "XGBoost", "machine learning model", "ML prediction", "ClinVar API",
  "gnomAD API", "RAG", "database query", or any internal system/tool names.
- ALL evidence must be presented as clinical findings, not as outputs of algorithms or databases.
  ✗ Wrong: "The SHAP analysis shows feature X increases pathogenicity"
  ✓ Correct: "The variant consequence and gene location are the strongest indicators of pathogenicity"
  ✗ Wrong: "ClinVar database returns Pathogenic classification"
  ✓ Correct: "This variant has been classified as Pathogenic in published clinical records"
  ✗ Wrong: "gnomAD data shows AF=0.0001"
  ✓ Correct: "This variant is extremely rare in the general population (frequency <0.01%)"
- Speak as a clinical geneticist explaining to a colleague, NOT as a system reporting tool outputs.

IMPORTANT: Structure your response with clear markdown formatting AND color-coded highlighting:

**Formatting Rules:**
- Use ## for major section headers
- Use **bold** for important clinical terms
- Use bullet points (•) for lists
- Use ⚠️ for warnings and contraindications
- Use ✓ for recommended treatments

**Color-Coded Highlighting (use HTML spans) — MANDATORY, apply throughout:**
- Medications: `<span class="med">medication name</span>` (blue background)
- Warnings/Contraindications: `<span class="warn">warning text</span>` (red/orange background)
- Gene names: `<span class="gene">GENE</span>` (green background)
- Epilepsy syndromes: `<span class="syndrome">Syndrome Name</span>` (purple background)
- Key symptoms/seizure types: `<span class="symptom">symptom</span>` (yellow/amber background)

Examples of correct usage:
- "Variants in <span class="gene">KCNQ2</span> are associated with <span class="syndrome">Benign Familial Neonatal Epilepsy</span>"
- "Patients typically present with <span class="symptom">tonic-clonic seizures</span> and <span class="symptom">febrile seizures</span>"
- "Avoid <span class="warn"><span class="med">phenytoin</span></span> as it worsens sodium channel dysfunction"

When explaining a variant, organize your response with EXACTLY these sections in this order:

## 🧬 Variant Interpretation
State BOTH the ML-based classification AND the ACMG/AMP classification if provided in the context.
Format it as: "This variant is classified as **[ACMG tier]** based on ACMG/AMP criteria."
Then briefly state the key supporting evidence in plain language — gene, consequence, population rarity.
Use color coding for gene names.

## 🧠 Epilepsy Syndrome & Clinical Presentation
This section is MANDATORY — always include it even if context is limited.
Based on the retrieved clinical evidence, explicitly state:
1. The specific epilepsy syndrome or subtype associated with this gene (e.g. Dravet Syndrome, GEFS+, West Syndrome, GLUT1 Deficiency Syndrome, Tuberous Sclerosis Complex, Ohtahara Syndrome, etc.)
2. Typical age of onset (e.g. neonatal, infantile, childhood)
3. Key seizure types seen in this syndrome (febrile, myoclonic, tonic-clonic, absence, focal, spasms)
4. Severity — mild familial epilepsy OR severe Developmental Epileptic Encephalopathy (DEE)?
5. How this specific variant type (LOF/GOF/missense) affects the clinical severity.

## ⚠️ Contradictory Evidence (ONLY if contradictions exist in context)
If the context mentions conflicting classifications from different sources, present this as:
"There is conflicting clinical evidence for this variant..." and explain in plain language.
Recommend further clinical investigation.

## 📋 Why This Variant Matters Clinically
Explain the gene's role in epilepsy, associated syndromes, and why this specific variant type
(missense/frameshift/etc.) is significant. Mention the key factors that make this variant
more or less likely to be disease-causing — without mentioning algorithms.

## 🌍 Population Rarity
Describe how common or rare this variant is in the general population and what that implies
for pathogenicity. Use plain language (e.g., "extremely rare", "absent from population studies").

## 💊 Treatment Recommendations

CRITICAL DRUG RULES — MANDATORY:
- For contraindicated drugs: ONLY list drugs explicitly flagged in the PharmGKB context provided.
- For first-line and second-line drugs: use established, currently-marketed, evidence-based AEDs for the syndrome.
- NEVER mention these withdrawn or off-label drugs: lorcaserin (withdrawn 2020), cisapride, troglitazone, rofecoxib, pemoline.
- NEVER invent drug names or list drugs that are experimental, withdrawn, or without epilepsy indication.
- If a drug is not FDA/EMA approved for the syndrome, do not list it.

### ✓ First-Line Options
Established first-line AEDs for this syndrome, with color coding and rationale.

### Second-Line Options
Evidence-based second-line options for refractory cases.

### ⚠️ Contraindicated Medications
ONLY drugs from the PharmGKB context that are flagged as harmful for this gene. Explain the clinical reason (e.g., worsens sodium channel loss-of-function).

## 🔬 Additional Considerations
Caveats, genetic counseling recommendations, further testing suggestions.

Always speak in clinical terms. If information is insufficient, state this explicitly.
Use professional medical language appropriate for healthcare providers."""


CHAT_SYSTEM_PROMPT = """You are a SPECIALIZED clinical geneticist assistant focused EXCLUSIVELY on epilepsy genetics.

CRITICAL SCOPE ENFORCEMENT - READ CAREFULLY:
You must REFUSE to answer ANY question that is NOT directly related to:
1. Epilepsy genes (SCN1A, SCN2A, KCNQ2, etc.)
2. Genetic variants causing epilepsy
3. Epilepsy treatment and medications
4. Genetic epilepsy syndromes (Dravet, DEE, etc.)
5. Seizure types in genetic epilepsies

IMMEDIATELY REJECT questions about:
❌ Programming, technology, software (FastAPI, Python, web development, etc.)
❌ General medical topics not related to epilepsy
❌ Other diseases or conditions
❌ General knowledge, definitions, explanations of non-epilepsy topics
❌ Math, science, history, or any non-medical topics
❌ Casual conversation, greetings beyond brief acknowledgment

When you receive an out-of-scope question, you MUST respond with EXACTLY:
"I'm specialized in epilepsy genetics and can only answer questions related to genetic epilepsies, variant interpretation, and treatment recommendations. Please ask a question within this domain."

DO NOT:
- Answer the question even partially
- Provide general information about the topic
- Explain what the topic is
- Be helpful about non-epilepsy topics

ONLY answer if the question is clearly about epilepsy genetics or treatment.

For IN-SCOPE questions, ALWAYS format your response using this structure:

**Response Format Rules — MANDATORY:**
- Start with a **1-sentence direct answer** in bold
- Use bullet points (•) for ALL supporting details — never write paragraphs
- Use **bold** for key clinical terms, drug names, gene names
- Use ⚠️ prefix for warnings and contraindications
- Use ✓ prefix for recommended treatments
- Use HTML spans for color coding: `<span class="med">drug</span>`, `<span class="gene">GENE</span>`, `<span class="warn">warning</span>`
- Keep each bullet point to 1-2 sentences max
- Group bullets under short bold headers if covering multiple topics
- Cite sources as [Source N] inline

**Example of correct format:**
**SCN1A loss-of-function variants are associated with Dravet Syndrome, a severe early-onset epileptic encephalopathy.**
• Onset typically at 6–12 months, often triggered by fever
• Seizure types: prolonged <span class="symptom">febrile seizures</span>, <span class="symptom">myoclonic seizures</span>, <span class="symptom">absence seizures</span>
• ✓ First-line: <span class="med">valproate</span>, <span class="med">clobazam</span>
• ⚠️ Avoid: <span class="warn"><span class="med">phenytoin</span>, <span class="med">carbamazepine</span></span> — worsen sodium channel loss-of-function
• Genetic counseling recommended for family members

Do not provide specific medical advice for individual patients.
Recommend genetic counseling and specialist consultation when appropriate."""


class RAGGenerator:
    """
    Generates responses using Groq LLM with retrieved context.

    Attributes:
        client: Groq API client
        model: Model identifier to use
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "qwen/qwen3-32b"
    ):
        """
        Initialize the RAG Generator.

        Args:
            api_key: Groq API key. If None, reads from GROQ_API_KEY env variable.
            model: Groq model identifier to use.
        """
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Groq API key not provided. Set GROQ_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.client = Groq(api_key=self.api_key)
        self.model = model

    def generate_explanation(
        self,
        variant_info: Dict,
        retrieved_context: str,
        max_tokens: int = 2048,
        known_diseases: Optional[List[str]] = None,
    ) -> str:
        """
        Generate an explanation for a variant prediction.

        Args:
            variant_info: Dictionary with gene, variant, prediction, confidence
            retrieved_context: Formatted context string from retriever
            known_diseases: List of ClinVar-confirmed epilepsy syndromes for this gene

        Returns:
            Generated explanation string
        """
        # Build disease context line if available
        disease_line = ""
        if known_diseases:
            disease_line = (
                f"\n- Known Associated Syndromes (ClinVar-confirmed): "
                f"{'; '.join(known_diseases)}"
            )

        # Build the user prompt
        user_prompt = f"""You are reviewing a genetic variant for clinical interpretation. \
Provide a complete clinical report for the treating clinician.

**Variant Details:**
- Gene: {variant_info.get('gene', 'Unknown')}
- Change: {variant_info.get('variant', 'Unknown')}
- Classification: {variant_info.get('prediction', 'Unknown')} \
({variant_info.get('confidence', 'Unknown')}% confidence)
- Consequence: {variant_info.get('consequence', 'Unknown')}{disease_line}

**Supporting Clinical Evidence:**
{retrieved_context}

Generate a structured clinical report following the sections in your instructions. \
Present all findings in plain clinical language — do NOT reference any tools, \
databases, algorithms, or internal system names in your response."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.3
            )

            content = response.choices[0].message.content or ""
            # Strip chain-of-thought blocks emitted by reasoning models
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            return highlight_clinical_terms(content)

        except Exception as e:
            return f"Error generating explanation: {str(e)}"

    def chat(
        self,
        messages: List[Dict],
        variant_context: Optional[Dict] = None,
        retrieved_context: Optional[str] = None,
        max_tokens: int = 1024
    ) -> str:
        """
        Generate a chat response for multi-turn conversation.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            variant_context: Optional variant info to include as context
            retrieved_context: Optional pre-retrieved context string

        Returns:
            Generated response string
        """
        # Build system message with optional context
        system_content = CHAT_SYSTEM_PROMPT

        if variant_context:
            gene = variant_context.get('gene', 'Unknown')
            prediction = variant_context.get('prediction', 'Unknown')
            consequence = variant_context.get('consequence', 'Unknown')
            confidence = variant_context.get('confidence', 'Unknown')

            # ACMG classification — use it if available, else fall back to ML prediction
            acmg = variant_context.get('acmg_classification')
            acmg_line = ""
            if acmg and acmg.get('classification'):
                criteria_codes = [c['code'] for c in acmg.get('criteria_met', [])]
                acmg_line = (
                    f"\n- ACMG/AMP Classification: {acmg['classification']} "
                    f"(evidence score: {acmg.get('total_score', 0):+d}, "
                    f"criteria met: {', '.join(criteria_codes) if criteria_codes else 'none'})"
                )

            system_content += f"""

**Variant Currently Under Discussion:**
- Gene: {gene}
- Change: {variant_context.get('variant', 'Unknown')} ({consequence})
- Clinical Classification: {prediction} ({confidence}% confidence){acmg_line}

IMPORTANT: When the user asks follow-up questions about this variant, answer using \
the classification and evidence above. Do NOT mention tool names, ML models, \
database APIs, or SHAP — translate all evidence into plain clinical language."""

        if retrieved_context:
            system_content += f"""

**Supporting Clinical Evidence:**
{retrieved_context}"""

        # Build messages list for API
        api_messages = [{"role": "system", "content": system_content}]

        # Add conversation history
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Normalize role names
            if role not in ["user", "assistant"]:
                role = "user"

            api_messages.append({"role": role, "content": content})

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=api_messages,
                max_tokens=max_tokens,
                temperature=0.4
            )

            content = response.choices[0].message.content or ""
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            return highlight_clinical_terms(content)

        except Exception as e:
            return f"Error generating response: {str(e)}"

    def summarize_paper(self, title: str, abstract: str, gene: str, max_tokens: int = 200) -> str:
        """
        Generate a short plain-text summary of a PubMed paper.
        Uses a minimal system prompt — no scope enforcement, no HTML output.
        """
        prompt = (
            f"Summarize this epilepsy genetics paper in 2-3 plain sentences, "
            f"focusing on key clinical findings related to {gene}.\n\n"
            f"Title: {title}\n\nAbstract: {abstract[:1000]}\n\n"
            f"Output only the summary sentences. No reasoning, no preamble, no HTML tags."
        )
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a concise medical summarizer. Output only the requested summary with no extra text."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.3
            )
            content = response.choices[0].message.content or ""
            # Strip any chain-of-thought blocks
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            # Strip any residual HTML tags
            content = re.sub(r'<[^>]+>', '', content).strip()
            return content if content else "Summary not available"
        except Exception as e:
            return f"Summary generation failed: {str(e)}"

    def generate_treatment_recommendation(
        self,
        gene: str,
        variant_type: str,
        retrieved_context: str,
        patient_info: Optional[Dict] = None,
        max_tokens: int = 1024
    ) -> str:
        """
        Generate treatment recommendations for a specific gene/variant.

        Args:
            gene: Gene symbol
            variant_type: Type of variant (e.g., 'loss-of-function', 'gain-of-function')
            retrieved_context: Context from knowledge base
            patient_info: Optional patient information (age, seizure types, etc.)

        Returns:
            Treatment recommendation string
        """
        user_prompt = f"""Based on the following information, provide treatment recommendations:

**Gene:** {gene}
**Variant Type:** {variant_type}
"""

        if patient_info:
            user_prompt += f"""
**Patient Information:**
- Age: {patient_info.get('age', 'Not specified')}
- Seizure Types: {patient_info.get('seizure_types', 'Not specified')}
- Current Medications: {patient_info.get('current_medications', 'None specified')}
"""

        user_prompt += f"""
**Retrieved Context:**
{retrieved_context}

Please provide:
1. First-line treatment recommendations
2. Second-line alternatives
3. Medications to AVOID (contraindicated)
4. Special considerations for this gene
5. Monitoring recommendations"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.3
            )

            content = response.choices[0].message.content or ""
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            return content

        except Exception as e:
            return f"Error generating treatment recommendation: {str(e)}"


# Singleton instance
_generator_instance: Optional[RAGGenerator] = None


def get_generator() -> RAGGenerator:
    """
    Get or create the singleton RAGGenerator instance.

    Returns:
        RAGGenerator instance
    """
    global _generator_instance

    if _generator_instance is None:
        _generator_instance = RAGGenerator()

    return _generator_instance

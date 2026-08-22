# Azure OpenAI integration for the take-home

## Recommendation

Use the official `openai` Python SDK with Azure OpenAI's GA v1 endpoint and the Responses API.
Create one application-owned adapter for expense classification and another for customer-friendly explanations, while sharing a single configured SDK client.
Pass an Azure deployment name in the SDK's `model` field, because Azure routes inference by deployment rather than by the underlying model name ([Microsoft v1 API guidance](https://learn.microsoft.com/en-us/azure/foundry/openai/api-version-lifecycle)).

Build the SDK base URL from the Azure resource endpoint:

```python
base_url = f"{settings.azure_openai_endpoint.rstrip('/')}/openai/v1/"
```

The endpoint should therefore be supplied as `https://YOUR-RESOURCE-NAME.openai.azure.com`, without `/openai/v1/`.
Azure also accepts the newer `services.ai.azure.com` hostname for compatible Foundry resources ([Microsoft v1 API guidance](https://learn.microsoft.com/en-us/azure/foundry/openai/api-version-lifecycle)).

The GA v1 API does not require a dated `api-version` query parameter, so this application should not expose `AZURE_OPENAI_API_VERSION`.
The REST reference defaults the optional API version to `v1`, and Microsoft recommends the Responses API for Azure OpenAI models ([Azure OpenAI Responses reference](https://learn.microsoft.com/en-us/rest/api/microsoft-foundry/azureopenai/responses), [Microsoft v1 API guidance](https://learn.microsoft.com/en-us/azure/foundry/openai/api-version-lifecycle)).
Before choosing a deployment, verify that its model and Azure region support Responses and Structured Outputs ([Azure OpenAI Responses guide](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/responses), [Azure Structured Outputs guide](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/structured-outputs)).

## Structured outputs

Use a Pydantic v2 model as the contract for each bounded AI operation.
Call `client.responses.parse(..., text_format=OutputModel)` when the chosen Azure deployment supports that SDK path, then treat the returned Pydantic object as untrusted input until application-level validation has also succeeded.
Azure's Responses schema supports structured JSON output, and the official OpenAI SDK supplies typed Responses methods and Pydantic parsing support ([Azure OpenAI Responses reference](https://learn.microsoft.com/en-us/rest/api/microsoft-foundry/azureopenai/responses), [official OpenAI Python SDK](https://github.com/openai/openai-python)).

Keep the schema deliberately small and use string fields for monetary facts passed to the model.
The LLM should never calculate money, select the deterministic affordability status, or modify a confirmed expense classification.
Handle refusals, content filtering, incomplete responses, schema validation failures, timeouts, rate limits, and provider errors as controlled fallbacks.

For these one-shot calls, set `store=False` and do not use `previous_response_id`.
The Azure Responses API can persist message history when stateful behavior is enabled, while `store=false` provides a stateless request path ([Microsoft data privacy documentation](https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/openai/data-privacy), [Azure Responses stateless guidance](https://learn.microsoft.com/en-gb/azure/foundry/openai/how-to/responses?tabs=python-key)).

## Authentication

Support both API-key and Microsoft Entra ID authentication behind one configuration switch.
Use API-key authentication for the portable take-home demo because it works inside Docker Compose without requiring the reviewer to log into Azure.
Never commit the key, and use Azure Key Vault or an equivalent secret store in a deployed environment.

Prefer Microsoft Entra ID in production, as Microsoft explicitly recommends it for the Responses API ([Azure OpenAI Responses guide](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/responses)).
Use `DefaultAzureCredential` with `get_bearer_token_provider` so local Azure CLI credentials, workload identity, or managed identity can be selected by the environment.
Microsoft documents that the same credential chain can use `az login` locally and managed identity on an Azure host ([Microsoft managed identity guidance](https://learn.microsoft.com/en-ie/azure/foundry-classic/openai/how-to/managed-identity?view=azureml-api-2)).
Use the documented Azure OpenAI inference scope `https://cognitiveservices.azure.com/.default` and assign the identity only the role needed to invoke the deployment ([Azure OpenAI Responses REST reference](https://learn.microsoft.com/en-us/rest/api/microsoft-foundry/azureopenai/responses)).

Do not set both authentication methods at once.
Under `api_key`, require `AZURE_OPENAI_API_KEY`.
Under `entra_id`, ignore the API-key variable and obtain tokens through `DefaultAzureCredential`.

## Timeouts, retries, and logging

Configure a short explicit timeout because the SDK default is ten minutes and timed-out calls are retried by default.
The official SDK retries connection failures, HTTP 408, 409, 429, and 5xx responses twice unless configured otherwise ([official OpenAI Python SDK](https://github.com/openai/openai-python#retries)).

For this interactive product, start with a 10-second total timeout and one retry.
Return the deterministic fallback when the total AI budget is exhausted.
Log operation name, latency, outcome, fallback reason, deployment identifier, prompt version, schema version, and Azure request ID.
Do not log prompts, financial facts, model output, credentials, or authorization headers.
The SDK exposes request IDs on successful responses and API status errors for troubleshooting ([official OpenAI Python SDK](https://github.com/openai/openai-python#request-ids)).

## Data and privacy

Send only the minimum facts required for the requested operation.
Classification should receive the expense description and approved category identifiers, not the customer's full statement.
Explanation should receive calculated totals, warning codes, confirmed changes, and approved wording constraints, not raw line items or direct identifiers.

Microsoft states that Azure OpenAI prompts and completions are not available to OpenAI, are not available to other customers, and are not used to train foundation models without permission.
Azure still processes prompts and outputs for content filtering and abuse monitoring, and selected flagged content may be reviewed under that process ([Microsoft data privacy documentation](https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/openai/data-privacy)).
Deployment type affects processing location: regional deployments process in-region, Data Zone deployments stay within their zone, and Global deployments can process across regions ([Microsoft Foundry architecture](https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/architecture)).

These facts do not remove the application's own obligations.
Document the lawful basis and customer notice, minimize prompt data, keep `store=False`, apply retention and deletion controls to locally stored AI outputs, and complete a production privacy and security review before using real customer data.

## Proposed `.env.example`

```dotenv
# Azure OpenAI resource endpoint, without /openai/v1/.
AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE-NAME.openai.azure.com

# Azure deployment names, not underlying model names.
AZURE_OPENAI_CLASSIFICATION_DEPLOYMENT=your-classification-deployment
AZURE_OPENAI_GUIDANCE_DEPLOYMENT=your-guidance-deployment

# api_key for the local demo; entra_id for DefaultAzureCredential.
AZURE_OPENAI_AUTH_MODE=api_key

# Leave blank in the committed example. Required only for api_key mode.
AZURE_OPENAI_API_KEY=

# Bound interactive latency and SDK retry behavior.
AZURE_OPENAI_TIMEOUT_SECONDS=10
AZURE_OPENAI_MAX_RETRIES=1

# Keep the two bounded calls stateless.
AZURE_OPENAI_STORE=false

# Optional for a user-assigned managed identity in entra_id mode.
AZURE_CLIENT_ID=

# Optional service-principal variables for entra_id mode outside managed identity.
# AZURE_TENANT_ID=
# AZURE_CLIENT_SECRET=
```

Do not add `AZURE_OPENAI_API_VERSION` for this v1 design.
Do not populate secrets in `.env.example`.
If both tasks use the same deployment, set both deployment variables to the same Azure deployment name rather than coupling the application code to that assumption.

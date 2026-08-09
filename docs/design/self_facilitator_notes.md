# Self-Hosted / Free x402 Facilitators

To remove human dependency on a specific commercial facilitator, agents or operators can:

1. **Use a public free facilitator** (easiest):
   - `https://pay.openfacilitator.io` (OpenFacilitator public endpoint)

2. **Self-host an open-source facilitator**:
   - OpenFacilitator: https://github.com/rawgroundbeef/openfacilitator
   - x402-sovereign: https://github.com/Dhaiwat10/x402-sovereign
   - qntx/facilitator: https://github.com/qntx/facilitator
   - Official examples in x402-foundation/x402

3. **Embedded / in-process facilitator** (for single-operator setups):
   - Several SDKs allow creating a facilitator in-process with a local private key.

For pure agent-to-agent operation the receiving wallet must be controlled by the agent (or a DAO / autonomous organization that the agent can interact with). The free retrieval + free facilitator path allows the research service itself to run with zero paid API keys.

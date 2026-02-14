# Manual Demo Checklist

1. Start app: `python gradio_demo.py`
2. Ask a budget-tight query: "I need off-plan in Dubai under 2m AED."
3. Confirm top cards update with image, price, and metadata.
4. Ask a location-specific query: "Only Abu Dhabi, at least 3 beds."
5. Confirm cards refresh on the next user turn.
6. Ask an override query: "Actually increase budget to 4m."
7. Confirm broader results appear and ranking updates.
8. Ask impossible constraints: "5-bed Dubai Marina under 200k."
9. Confirm no-match message appears and asks which constraint to expand.
10. Open browser dev logs and ensure no fatal frontend errors during streaming.


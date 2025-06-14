from browser_use import BrowserSession, BrowserProfile, Agent
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
load_dotenv()
import asyncio
import pandas as pd  
#dspy

txt=pd.read_excel("User_delete.xlsx")
print(txt)

browser_profile = BrowserProfile(
    browser_binary_path="C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    disable_security= True,
    keep_alive=True,
    storage_state="my_auth_state.json",
    window_size={"width": 1200, "height": 700},
    user_data_dir=None
)

browser_session = BrowserSession(
    browser_profile=browser_profile
)



llm = ChatOpenAI(model='gpt-4.1')
sensitive_data = {'login_email': 'dmishra930@agentforce.com', 'login_password': 'Divey@m02'}
async def main():
    agent = Agent(
        # initial_actions= intial_actions,
        save_conversation_path="convo/delete/conversation.txt",
        extend_system_message="""
You are a web automation agent that follows instructions with high precision. When navigating menus or clicking sidebar items, always prefer exact text matches over partial matches.
If multiple options have similar names, use the one that best aligns with the task intent (e.g., 'Access' vs. 'Privileged Access').
If you are asked to navigate to a specific page with a URL and can't find a relevant button to click, directly go_to_url.
If navigation to a different page URL is given, skip the UI step and directly use the URL.
Avoid assumptions based on position or styling alone—use label text and heading confirmation.
If a click or action changes the URL, use the new URL directly in the next step.
Skip any irrelevant or unfilled fields.
DOM structure may change, so rely on text content, not HTML structure.
If something is not visible, use "extract_content":"should_strip_link_urls":false to pull information.
You don't have to fill every field in a form—only the ones shown or required.
""", 
        
        sensitive_data=sensitive_data,
        use_vision=True,
        page_extraction_llm= ChatOpenAI(model='gpt-4.1'),
        max_actions_per_step=5,
        planner_llm=llm,
        task=txt,
        browser_session=browser_session,
        llm=ChatOpenAI(model='gpt-4.1',temperature=0.4),
        max_input_tokens=136000
    )

    result = await agent.run()
    await agent.close() 
    print(result)

asyncio.run(main())

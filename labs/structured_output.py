import os
import json

from openai import OpenAI
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

load_dotenv()

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

MAX_ATTEMPTS=2

class CharacterCard(BaseModel):
    nick_name:str = Field(min_length=1)
    nature: str = Field(min_length=1, description="性格，一句话")
    catchphrase: str = Field(description="口头禅")
    tone: float = Field(ge=0, le=1, description="0 温柔，1 毒舌")

BROKEN_EXAMPLE = True

def build_schema_example():
    if BROKEN_EXAMPLE:
        return '{"nick_name": "大肥鱼", "nature": "嘴毒心软的广东女孩","catchphrase": "你这个笨蛋"}'
    return '{"nick_name": "大肥鱼", "nature": "嘴毒心软的广东女孩","catchphrase": "你这个笨蛋", "tone": 0.5}'

def make_system_prompt():
    # 字段清单：BROKEN_EXAMPLE 时把 tone 的所有痕迹（示例+清单）都删掉，模型才会真的缺字段
    constraints = """- nick_name: 字符串，不能为空
- nature: 字符串，一句话性格，不能为空
- catchphrase: 字符串，口头禅"""
    if not BROKEN_EXAMPLE:
        constraints += "\n- tone: 数字（不是字符串），0 到 1 之间，0 温柔，1 毒舌"
    return f"""
你是一个角色卡生成器，请根据用户的性格描述，生成一张角色卡。

只返回如下结构的 json 对象，不要任何解释文字：

{build_schema_example()}

字段约束：
{constraints}

再次强调：只返回 json，不要任何解释文字。

""".strip()


def call_llm(messages):
    return client.chat.completions.create(
        model="deepseek-chat",  # json_object 模式用 chat 模型更稳
        messages=messages,
        response_format={"type": "json_object"},
    )



def parse_and_validate(content):
    data = json.loads(content)          # 语法关：括号、引号、逗号
    card = CharacterCard.model_validate(data)
    print(card.nick_name, card.tone, type(card.tone))
    return card

def generate_card(user_input):
    messages = [
        {"role": "system", "content": make_system_prompt()},
        {"role": "user", "content": user_input},
    ]

    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        raw = ""
        try:
            response = call_llm(messages)
            raw = response.choices[0].message.content
            print(f"[attempt {attempt}] 模型原始值返回{raw}")
            card = parse_and_validate(raw)
            return card
        except json.JSONDecodeError as e:
            last_error = f"JSON 语法错误：{e}"
            print(f"[attempt{attempt}] 语法未通过：{last_error}")
        except ValidationError as e:
            # 语义层失败：语法没问题，但字段/类型/范围不合规
            last_error = str(e)
            print(f"[attempt {attempt}] 语义关未通过:\n{e}")

        messages.append({"role": "assistant", "content": raw})
        messages.append({
            "role": "user",
            "content": (
                f"上次输出不合法，pydantic 给出：\n{last_error}\n"
                f"正确的 schema 是：{CharacterCard.model_json_schema()}\n"
                "请只返回符合 schema 的 json。"
            ),
        })

    raise RuntimeError(f"重试 {MAX_ATTEMPTS} 次后仍失败，最后一次错误：{last_error}")

if __name__ == "__main__":
    card = generate_card("一个温柔但偶尔毒舌的上海阿姨")
    print("=" * 40)
    print(f"nick_name: {card.nick_name}")
    print(f"nature:    {card.nature}")
    print(f"catchphrase: {card.catchphrase}")
    print(f"tone:      {card.tone}, type: {type(card.tone)}")
    print("=" * 40)
    # print("校验通过：tone 是 float，能比大小、能排序、能算平均值")
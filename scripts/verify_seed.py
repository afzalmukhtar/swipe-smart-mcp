from sqlmodel import Session, select, create_engine
from src import CreditCard, RewardRule, engine


def verify():
    with Session(engine) as session:
        # Check Cards
        cards = session.exec(select(CreditCard)).all()
        print(f"Found {len(cards)} cards.")
        amazon_cards = [c for c in cards if "Amazon" in c.name]
        for card in amazon_cards:
            print(f"Card: {card.name}, Meta: {card.meta_data}")

        # Check Rules
        rules = session.exec(
            select(RewardRule).where(RewardRule.condition_expression != None)
        ).all()
        print(f"Found {len(rules)} conditional rules.")
        for rule in rules:
            print(
                f"Rule Category: {rule.category}, Condition: {rule.condition_expression} (Card ID: {rule.card_id})"
            )


if __name__ == "__main__":
    verify()

# Developer 라는 개발자 클래스를 정의하려고함.
# 내부에 id, title, skill 변수가 있고, 이 내용을 출력하는
# printinfo()매서드가 필요해
class Developer:
    def __init__(self, id, title, skill):
        self.id = id
        self.title = title
        self.skill = skill

    def printinfo(self):
        print(f"ID: {self.id}, Title: {self.title}, Skill: {self.skill}")

# 인스턴스를 생성
dev1 = Developer(1, "Frontend", "React")
dev2 = Developer(2, "Backend", "Django")

dev1.printinfo()
dev2.printinfo()   

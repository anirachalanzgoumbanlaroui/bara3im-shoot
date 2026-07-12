import random

class MotivationService:
    @staticmethod
    def get_message(attendance, performance, goal=50):
        # 1. No attendance
        if not attendance:
            return {
                "en": "We're waiting for you today. Let's make it a great shift!",
                "ar": "نحن بانتظارك اليوم. دعنا نجعلها مناوبة رائعة!"
            }
        
        photos = performance.photo_count if performance else 0
        if goal <= 0:
            goal = 50
        percentage = photos / goal
        
        if percentage < 0.25:
            en_options = [
                "Let's start strong!",
                "Ready to shoot some great photos?",
                "Make today count!",
                "Step up to the starting line!"
            ]
            ar_options = [
                "لنبدأ بقوة!",
                "جاهز لالتقاط صور رائعة؟",
                "اجعل اليوم مميزًا!",
                "خطوة إلى خط البداية!"
            ]
        elif percentage < 0.50:
            en_options = [
                "Nice beginning.",
                "Good start, keep moving forward!",
                "Awesome, you're on the move!",
                "First coin collected! Keep it up."
            ]
            ar_options = [
                "بداية رائعة.",
                "بداية جيدة، واصل التقدم!",
                "رائع، أنت في حركة مستمرة!",
                "جمعت أول عملة ذهبية! استمر."
            ]
        elif percentage < 0.75:
            en_options = [
                "You're halfway there.",
                "Halfway to the goal! Keep it up.",
                "Great progress, keep going!",
                "Looking good! Halfway to the finish flag."
            ]
            ar_options = [
                "لقد قطعت نصف الطريق.",
                "نصف الطريق إلى الهدف! استمر.",
                "تقدم رائع، واصل العمل!",
                "تبدو رائعاً! منتصف الطريق إلى راية النهاية."
            ]
        elif percentage < 1.0:
            en_options = [
                "You're almost there.",
                "Just a few more photos to hit the goal!",
                "You've got this! Almost there.",
                "The goal pole is in sight!"
            ]
            ar_options = [
                "لقد اقتربت من الوصول.",
                "بضع صور أخرى فقط للوصول إلى الهدف!",
                "أنت قادر على ذلك! اقتربت.",
                "سارية الهدف في الأفق!"
            ]
        elif percentage < 1.20:
            en_options = [
                "Congratulations! Goal achieved.",
                "Goal reached! Excellent work.",
                "Fantastic job! Goal complete.",
                "You grabbed the top of the goal pole! Superb!"
            ]
            ar_options = [
                "تهانينا! تم تحقيق الهدف.",
                "تم الوصول إلى الهدف! عمل ممتاز.",
                "عمل رائع! اكتمل الهدف.",
                "لقد أمسكت بأعلى سارية الهدف! رائع!"
            ]
        elif percentage < 1.50:
            en_options = [
                "Outstanding performance!",
                "You are doing amazing today!",
                "Exceeding expectations! Keep it up.",
                "Fire flower power! You're blazing through!"
            ]
            ar_options = [
                "أداء متميز!",
                "أنت تقوم بعمل مذهل اليوم!",
                "تجاوزت التوقعات! واصل التقدم.",
                "قوة زهرة النار! أنت تتألق!"
            ]
        else:
            en_options = [
                "You're unstoppable today!",
                "Power up! Unstoppable performance.",
                "Super Mario mode activated! Legendary!",
                "Star power-up! Invincible!"
            ]
            ar_options = [
                "لا يمكن إيقافك اليوم!",
                "طاقة كاملة! أداء لا يمكن إيقافه.",
                "تم تفعيل وضع سوبر ماريو! أسطوري!",
                "قوة النجم الخارق! لا يقهر!"
            ]
            
        # Select randomly but deterministically if possible (using day/photos or just standard random)
        idx = random.randint(0, len(en_options) - 1)
        return {
            "en": en_options[idx],
            "ar": ar_options[idx]
        }

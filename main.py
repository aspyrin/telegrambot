import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.utils import deep_linking

logging.basicConfig(level=logging.INFO)
from quizzer import Quiz


TOKEN = 'your_token'
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

quizzes_database = {}  # здесь хранится информация о викторинах
quizzes_owners = {}  # здесь хранятся пары "id викторины <—> id её создателя"


# Хэндлер на команду /start
@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    if message.chat.type == types.ChatType.PRIVATE:
        poll_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        poll_keyboard.add(types.KeyboardButton(text="Создать викторину",
                                               request_poll=types.KeyboardButtonPollType(type=types.PollType.QUIZ)))
        poll_keyboard.add(types.KeyboardButton(text="Отмена"))
        await message.answer("Нажмите на кнопку ниже и создайте викторину! "
                             "Внимание: в дальнейшем она будет публичной (неанонимной).", reply_markup=poll_keyboard)
    else:
        words = message.text.split()
        # Только команда /start без параметров. В этом случае отправляем в личку с ботом.
        if len(words) == 1:
            bot_info = await bot.get_me()            # Получаем информацию о нашем боте
            keyboard = types.InlineKeyboardMarkup()  # Создаём клавиатуру с URL-кнопкой для перехода в ЛС
            move_to_dm_button = types.InlineKeyboardButton(text="Перейти в ЛС",
                                                           url=f"t.me/{bot_info.username}?start=anything")
            keyboard.add(move_to_dm_button)
            await message.reply("Не выбрана ни одна викторина. Пожалуйста, перейдите в личные сообщения с ботом, "
                                "чтобы создать новую.", reply_markup=keyboard)
        # Если у команды /start или /startgroup есть параметр, то это, скорее всего, ID викторины.
        # Проверяем и отправляем.
        else:
            quiz_owner = quizzes_owners.get(words[1])
            if not quiz_owner:
                await message.reply("Викторина удалена, недействительна или уже запущена в другой группе. Попробуйте создать новую.")
                return
            for saved_quiz in quizzes_database[quiz_owner]:  # Проходим по всем сохранённым викторинам от конкретного user ID
                if saved_quiz.quiz_id == words[1]:  # Нашли нужную викторину, отправляем её.
                    msg = await bot.send_poll(chat_id=message.chat.id, question=saved_quiz.question,
                                        is_anonymous=False, options=saved_quiz.options, type="quiz",
                                        correct_option_id=saved_quiz.correct_option_id)
                    quizzes_owners[msg.poll.id] = quiz_owner  # ID викторины при отправке уже другой, создаём запись.
                    del quizzes_owners[words[1]]              # Старую запись удаляем.
                    saved_quiz.quiz_id = msg.poll.id          # В "хранилище" викторин тоже меняем ID викторины на новый
                    saved_quiz.chat_id = msg.chat.id          # ... а также сохраняем chat_id ...
                    saved_quiz.message_id = msg.message_id    # ... и message_id для последующего закрытия викторины.


# Хэндлер на текстовое сообщение с текстом “Отмена”
@dp.message_handler(lambda message: message.text == "Отмена")
async def action_cancel(message: types.Message):
    remove_keyboard = types.ReplyKeyboardRemove()
    await message.answer("Действие отменено. Введите /start, чтобы начать заново.", reply_markup=remove_keyboard)


@dp.message_handler(content_types=["poll"])
async def msg_with_poll(message: types.Message):
    # Если юзер раньше не присылал запросы, выделяем под него запись
    if not quizzes_database.get(str(message.from_user.id)):
        quizzes_database[str(message.from_user.id)] = []

    # Если юзер решил вручную отправить не викторину, а опрос, откажем ему.
    if message.poll.type != "quiz":
        await message.reply("Извините, я принимаю только викторины (quiz)!")
        return

    # Сохраняем себе викторину в память
    quizzes_database[str(message.from_user.id)].append(Quiz(
        quiz_id=message.poll.id,
        question=message.poll.question,
        options=[o.text for o in message.poll.options],
        correct_option_id=message.poll.correct_option_id,
        owner_id=message.from_user.id)
    )
    # Сохраняем информацию о её владельце для быстрого поиска в дальнейшем
    quizzes_owners[message.poll.id] = str(message.from_user.id)

    await message.reply(
        f"Викторина сохранена. Общее число сохранённых викторин: {len(quizzes_database[str(message.from_user.id)])}")


@dp.inline_handler()  # Обработчик любых инлайн-запросов
async def inline_query(query: types.InlineQuery):
    results = []
    user_quizzes = quizzes_database.get(str(query.from_user.id))
    if user_quizzes:
        for quiz in user_quizzes:
            keyboard = types.InlineKeyboardMarkup()
            start_quiz_button = types.InlineKeyboardButton(
                text="Отправить в группу",
                url=await deep_linking.get_startgroup_link(quiz.quiz_id)
            )
            keyboard.add(start_quiz_button)
            results.append(types.InlineQueryResultArticle(
                id=quiz.quiz_id,
                title=quiz.question,
                input_message_content=types.InputTextMessageContent(
                    message_text="Нажмите кнопку ниже, чтобы отправить викторину в группу."),
                reply_markup=keyboard
            ))
    await query.answer(switch_pm_text="Создать викторину", switch_pm_parameter="_",
                       results=results, cache_time=120, is_personal=True)


@dp.message_handler(commands=["test"])
async def cmd_test(message: types.Message):
    markup = types.InlineKeyboardMarkup()
    for q in quizzes_database[str(message.from_user.id)]:
        quiz_id = str(q.quiz_id)
        url = f'https://t.me/Aspyrin0001Bot?startgroup={quiz_id}'
        markup.add(types.InlineKeyboardButton(f"Go to quiz id={quiz_id}", url=url))
    await message.answer(f"Go to quizzes", reply_markup=markup)


# @dp.message_handler()
# async def echo(message: types.Message):
#     """sympl echo-bot"""
#     await message.reply(message.text)


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)

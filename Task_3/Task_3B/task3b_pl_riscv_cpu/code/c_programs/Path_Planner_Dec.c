/*
* Logic Quest (LQ): Task 3A Path Planner with Decryption
*
* Computes the shortest path on the Logic Quest arena (nodes N1..N36), with the
* line weights of Figure 1 on the Task 3A page: straight line 5, ring arcs
* 7 / 11 / 15 / 19 (inner ring to outermost ring), wavy line N1-N36 100.
*
* Inputs : current_node, next_node, is_encrypted
*   current_node     : where the bot is, 1..36. The path starts here.
*                      At the first location the bot is in the start box, N35.
*   is_encrypted = 0 : next_node is a node number.
*                      Path: current_node -> next_node.
*   is_encrypted = 1 : next_node is the 8-byte encrypted code, encrypted with
*                      PRESENT-80.
*                      Path: current_node -> the drop node in the block.
*
* Decrypted code (8 bytes, byte 0 first):
*   byte 0     : done flag (1 = last block: no pick-up after this drop)
*   byte 1..5  : message, 5 ASCII characters (0x00 = no character)
*   byte 6     : next pick-up node 1..36 (not used when the done flag is 1)
*   byte 7     : drop node 1..36 for this block
*   e.g. message "HELLO", drop at N26, then pick up at N12
*        -> 00 48 45 4C 4C 4F 0C 1A = 0048454C4C4F0C1A
*
* Outputs:
*   is_encrypted = 0 : the path from current_node to next_node.
*   is_encrypted = 1 : the message (message[]) and the path from current_node
*                      to the drop node. When the done flag is 0, the inputs
*                      for the next run are written too:
*                          IS_ENCRYPTED = 0
*                          CURRENT_NODE = the drop node
*                          NEXT_NODE    = the next pick-up node
*                      When the done flag is 1, the inputs are left as they are.
*
* Output (PC), read by test.sh line by line:
*   is_encrypted = 0     is_encrypted = 1, done = 0     is_encrypted = 1, done = 1
*   35                   Message : HELLO                Message : BYE
*   ...                  7                              7
*   7                    ...                            ...
*                        26                             26
*                        Next current_node : 26         Done
*                        Next next_node : 12
*   The path is one node per line, first node first. The message line shows
*   the non-zero message bytes as characters. The code at the end of main
*   prints all of this from message[], path_planned[], idx and the inputs
*   written for the next run.
*
* Debug prints: start every debug line with "dbg:" (see Functions Usage
*   below). test.sh and the evaluator skip the lines that start with "dbg:".
*   Any other extra line counts as part of your output and makes it wrong.
*
* PRESENT-80 (the cipher used for the encrypted codes):
*   block 64 bits, key 80 bits = A1 B2 C3 D4 E5 F6 07 18 29 3A (PRESENT_KEY_* below),
*   31 rounds. See the Task 3A page for the full description of the encryption;
*   your program has to do the reverse.
*
* Data memory ranges (used on the RISC-V CPU, Task 3B):
*   0x02000000 .. 0x0200000F : inputs
*   0x02000010 .. 0x0200001F : outputs (0x0200001C = CPU_DONE)
*   0x02000020 and up        : working memory, stack at the top
*
* Inputs  : ENCRYPTED_HI (0x02000000)  encrypted block, bytes 0..3 (first 8 hex digits)
*           ENCRYPTED_LO (0x02000004)  encrypted block, bytes 4..7 (last 8 hex digits)
*           IS_ENCRYPTED (0x02000008)  0 or 1                            } written for
*           NEXT_NODE    (0x0200000C)  next node, when IS_ENCRYPTED = 0   } the next run
*           CURRENT_NODE (0x0200000D)  current node (where the bot is)    } when done = 0
* Outputs : MESSAGE_0..4 (0x02000010 .. 0x02000014)  message, block bytes 1..5
*           NODE_POINT   (0x02000018)  every node of the path, written in order
*           CPU_DONE     (0x0200001C)  = 1 when finished
*
* Make sure you don't change anything outside the "Add your code here" sections.
*/

#include <stdlib.h>
#include <stdbool.h>
#include <stdint.h>
#include <limits.h>

// PRESENT-80 key: A1 B2 C3 D4 E5 F6 07 18 29 3A
#define PRESENT_KEY_HI  0xA1B2C3D4   // key bits 79..48
#define PRESENT_KEY_MID 0xE5F60718   // key bits 47..16
#define PRESENT_KEY_LO  0x293A       // key bits 15..0

#ifdef __linux__ // for host pc

    #include <stdio.h>

    void _put_byte(char c) { putchar(c); }

    void _put_str(char *str) {
        while (*str) {
            _put_byte(*str++);
        }
    }

    void print_output(uint8_t num) {
        if (num == 0) {
            putchar('0'); // if the number is 0, directly print '0'
            _put_byte('\n');
            return;
        }

        // convert the integer to a string
        char buffer[20];
        uint8_t index = 0;

        while (num > 0) {
            buffer[index++] = '0' + num % 10; // convert the last digit to its character representation
            num /= 10;                        // move to the next digit
        }
        // print the characters in reverse order (from right to left)
        while (index > 0) { putchar(buffer[--index]); }
        _put_byte('\n');
    }

    void _put_value(uint8_t val) { print_output(val); }

    // print a 32-bit value as 8 hex digits and a newline (e.g. the decrypted block)
    void _put_hex(uint32_t val) { printf("%08X\n", (unsigned int)val); }

    // read 16 hex digits into two 32-bit words, returns 0 if the text is not 16 hex digits
    int read_block(const char *hex, uint32_t *hi, uint32_t *lo) {
        uint32_t word[2] = { 0, 0 };
        if (hex[0] == '0' && (hex[1] == 'x' || hex[1] == 'X')) hex += 2;
        for (int n = 0; n < 16; n++) {
            char c = hex[n];
            uint32_t d;
            if      (c >= '0' && c <= '9') d = c - '0';
            else if (c >= 'a' && c <= 'f') d = c - 'a' + 10;
            else if (c >= 'A' && c <= 'F') d = c - 'A' + 10;
            else return 0;
            word[n >> 3] = (word[n >> 3] << 4) | d;
        }
        if (hex[16] != '\0') return 0;
        *hi = word[0];
        *lo = word[1];
        return 1;
    }

    /*
     * On the PC there is no data memory at 0x02000000, so MEM32(address) is a
     * normal array (one entry per 32-bit word). On the CPU it is the real
     * data memory. Either way, MEM32(0x02000020) reads the same place.
     */
    static uint32_t pc_data_mem[128];
    #define MEM32(addr)  (pc_data_mem[((addr) - 0x02000000u) >> 2])

#else  // for the test device

    void _put_byte(char c) { }
    void _put_value(uint8_t val) { }
    void _put_hex(uint32_t val) { }
    void _put_str(char *str) { }

    #define MEM32(addr)  (*(volatile uint32_t *)(addr))

#endif

/*
Functions Usage

To print while debugging, use the functions below, not printf().
On the PC they print. On the CPU they are empty, so they cost nothing there
and the same file still builds with generatehex.sh.

for a character: _put_byte('A');                        (putchar() on the PC)
for newline:     _put_byte('\n');
for string:      _put_str("your string here");
for number:      _put_value(your_number_here);           0 to 255, then a newline
for 32 bits:     _put_hex(your_32_bit_value_here);       8 hex digits, then a newline

Start every debug line with "dbg:" and end it with a newline (_put_value
and _put_hex end the line for you). test.sh and the evaluator skip the
lines that start with "dbg:", so these prints can stay in the file you
submit. Any other line you print counts as part of your output (see
"Output (PC)" at the top) and makes it wrong.

Examples:
        _put_str("dbg: start_point = ");     _put_value(start_point);
        _put_str("dbg: end_point = ");       _put_value(end_point);
        _put_str("dbg: ENCRYPTED_HI = ");    _put_hex(ENCRYPTED_HI);    // encrypted block, bytes 0..3
        _put_str("dbg: ENCRYPTED_LO = ");    _put_hex(ENCRYPTED_LO);    // encrypted block, bytes 4..7
        _put_str("dbg: first character = "); _put_byte(message[0]); _put_byte('\n');
        _put_str("dbg: Hello World!\n");

*/

// Custom Functions

// ############# Add your code here #############

static uint8_t get_neighbors(uint8_t u, uint8_t *nbrs, uint8_t *weights) {
    switch (u) {
        case 1:
            nbrs[0] = 5;  weights[0] = 5;
            nbrs[1] = 4;  weights[1] = 15;
            nbrs[2] = 6;  weights[2] = 15;
            nbrs[3] = 36; weights[3] = 100;
            return 4;
        case 2:
            nbrs[0] = 4;  weights[0] = 5;
            return 1;
        case 3:
            nbrs[0] = 6;  weights[0] = 5;
            return 1;
        case 4:
            nbrs[0] = 1;  weights[0] = 15;
            nbrs[1] = 2;  weights[1] = 5;
            nbrs[2] = 14; weights[2] = 15;
            return 3;
        case 5:
            nbrs[0] = 1;  weights[0] = 5;
            nbrs[1] = 7;  weights[1] = 11;
            nbrs[2] = 8;  weights[2] = 11;
            return 3;
        case 6:
            nbrs[0] = 1;  weights[0] = 15;
            nbrs[1] = 3;  weights[1] = 5;
            return 2;
        case 7:
            nbrs[0] = 5;  weights[0] = 11;
            nbrs[1] = 10; weights[1] = 5;
            nbrs[2] = 15; weights[2] = 11;
            return 3;
        case 8:
            nbrs[0] = 5;  weights[0] = 11;
            nbrs[1] = 11; weights[1] = 5;
            nbrs[2] = 20; weights[2] = 11;
            return 3;
        case 9:
            nbrs[0] = 11; weights[0] = 7;
            nbrs[1] = 12; weights[1] = 5;
            return 2;
        case 10:
            nbrs[0] = 7;  weights[0] = 5;
            return 1;
        case 11:
            nbrs[0] = 8;  weights[0] = 5;
            nbrs[1] = 9;  weights[1] = 7;
            nbrs[2] = 19; weights[2] = 7;
            return 3;
        case 12:
            nbrs[0] = 9;  weights[0] = 5;
            return 1;
        case 13:
            nbrs[0] = 14; weights[0] = 5;
            nbrs[1] = 30; weights[1] = 19;
            return 2;
        case 14:
            nbrs[0] = 4;  weights[0] = 15;
            nbrs[1] = 13; weights[1] = 5;
            nbrs[2] = 15; weights[2] = 5;
            return 3;
        case 15:
            nbrs[0] = 7;  weights[0] = 11;
            nbrs[1] = 14; weights[1] = 5;
            return 2;
        case 16:
            nbrs[0] = 17; weights[0] = 5;
            nbrs[1] = 23; weights[1] = 7;
            return 2;
        case 17:
            nbrs[0] = 16; weights[0] = 5;
            return 1;
        case 18:
            nbrs[0] = 19; weights[0] = 5;
            return 1;
        case 19:
            nbrs[0] = 11; weights[0] = 7;
            nbrs[1] = 18; weights[1] = 5;
            return 2;
        case 20:
            nbrs[0] = 8;  weights[0] = 11;
            nbrs[1] = 21; weights[1] = 5;
            nbrs[2] = 27; weights[2] = 11;
            return 3;
        case 21:
            nbrs[0] = 20; weights[0] = 5;
            return 1;
        case 22:
            nbrs[0] = 25; weights[0] = 5;
            return 1;
        case 23:
            nbrs[0] = 16; weights[0] = 7;
            nbrs[1] = 25; weights[1] = 7;
            nbrs[2] = 26; weights[2] = 5;
            return 3;
        case 24:
            nbrs[0] = 27; weights[0] = 5;
            return 1;
        case 25:
            nbrs[0] = 22; weights[0] = 5;
            nbrs[1] = 23; weights[1] = 7;
            return 2;
        case 26:
            nbrs[0] = 23; weights[0] = 5;
            nbrs[1] = 29; weights[1] = 11;
            return 2;
        case 27:
            nbrs[0] = 20; weights[0] = 11;
            nbrs[1] = 24; weights[1] = 5;
            nbrs[2] = 29; weights[2] = 11;
            return 3;
        case 28:
            nbrs[0] = 31; weights[0] = 5;
            nbrs[1] = 32; weights[1] = 15;
            return 2;
        case 29:
            nbrs[0] = 26; weights[0] = 11;
            nbrs[1] = 27; weights[1] = 11;
            nbrs[2] = 32; weights[2] = 5;
            return 3;
        case 30:
            nbrs[0] = 13; weights[0] = 19;
            nbrs[1] = 33; weights[1] = 5;
            nbrs[2] = 35; weights[2] = 19;
            return 3;
        case 31:
            nbrs[0] = 28; weights[0] = 5;
            nbrs[1] = 34; weights[1] = 5;
            nbrs[2] = 35; weights[2] = 19;
            return 3;
        case 32:
            nbrs[0] = 28; weights[0] = 15;
            nbrs[1] = 29; weights[1] = 5;
            return 2;
        case 33:
            nbrs[0] = 30; weights[0] = 5;
            return 1;
        case 34:
            nbrs[0] = 31; weights[0] = 5;
            return 1;
        case 35:
            nbrs[0] = 30; weights[0] = 19;
            nbrs[1] = 31; weights[1] = 19;
            return 2;
        case 36:
            nbrs[0] = 1;  weights[0] = 100;
            return 1;
        default:
            return 0;
    }
}

static uint64_t present_decrypt(uint64_t cipher, uint64_t key_hi64, uint16_t key_lo16) {
    uint8_t sbox[16];
    uint8_t inv_sbox[16];
    sbox[0] = 0xC; sbox[1] = 0x5; sbox[2] = 0x6; sbox[3] = 0xB;
    sbox[4] = 0x9; sbox[5] = 0x0; sbox[6] = 0xA; sbox[7] = 0xD;
    sbox[8] = 0x3; sbox[9] = 0xE; sbox[10] = 0xF; sbox[11] = 0x8;
    sbox[12] = 0x4; sbox[13] = 0x7; sbox[14] = 0x1; sbox[15] = 0x2;

    for (uint8_t i = 0; i < 16; i++) {
        inv_sbox[sbox[i]] = i;
    }

    uint64_t k_hi = key_hi64;
    uint16_t k_lo = key_lo16;

    for (uint8_t r = 1; r <= 31; r++) {
        uint64_t old_hi = k_hi;
        uint16_t old_lo = k_lo;
        k_hi = (old_hi >> 19) | ((uint64_t)old_lo << 45) | (old_hi << 61);
        k_lo = (uint16_t)(old_hi >> 3);
        k_hi = (k_hi & 0x0FFFFFFFFFFFFFFFULL) | ((uint64_t)sbox[k_hi >> 60] << 60);
        k_hi ^= (uint64_t)(r >> 1);
        k_lo ^= (uint16_t)((r & 1) << 15);
    }

    uint64_t state = cipher ^ k_hi;

    for (uint8_t r = 31; r >= 1; r--) {
        k_hi ^= (uint64_t)(r >> 1);
        k_lo ^= (uint16_t)((r & 1) << 15);
        k_hi = (k_hi & 0x0FFFFFFFFFFFFFFFULL) | ((uint64_t)inv_sbox[k_hi >> 60] << 60);
        uint64_t wrap19 = k_hi >> 45;
        k_hi = (k_hi << 19) | ((uint64_t)k_lo << 3) | (wrap19 >> 16);
        k_lo = (uint16_t)(wrap19 & 0xFFFF);

        uint64_t inv_p = 0;
        for (uint8_t i = 0; i < 64; i++) {
            if ((state >> i) & 1ULL) {
                uint8_t target = (i == 63) ? 63 : (((i & 0xF) << 2) | (i >> 4));
                inv_p |= (1ULL << target);
            }
        }
        state = inv_p;

        uint64_t s = 0;
        for (uint8_t n = 0; n < 16; n++) {
            uint8_t nibble = (uint8_t)((state >> (n << 2)) & 0xF);
            s |= ((uint64_t)inv_sbox[nibble]) << (n << 2);
        }
        state = s;

        state ^= k_hi;
    }

    return state;
}

// ##############################################

// main function
int main(int argc, char const *argv[]) {

    #ifdef __linux__

        if (argc < 4) {
            _put_str("usage: ./Path_Planner_Dec <current_node> <next_node> <is_encrypted>\n");
            _put_str("       current_node     : where the bot is, e.g. 35 (the start box)\n");
            _put_str("       is_encrypted = 0 : next_node is a node number, e.g. 7\n");
            _put_str("       is_encrypted = 1 : next_node is the encrypted code, 16 hex digits\n");
            return 1;
        }
        uint8_t  CURRENT_NODE        = atoi(argv[1]);
        uint8_t  IS_ENCRYPTED        = atoi(argv[3]);
        uint8_t  NEXT_NODE           = 0;
        uint32_t ENCRYPTED_HI        = 0;
        uint32_t ENCRYPTED_LO        = 0;
        if (IS_ENCRYPTED) {
            if (!read_block(argv[2], &ENCRYPTED_HI, &ENCRYPTED_LO)) {
                _put_str("with is_encrypted = 1, next_node must be exactly 16 hex digits\n");
                return 1;
            }
        }
        else {
            NEXT_NODE = atoi(argv[2]);
        }
        uint8_t MESSAGE_0           = 0;
        uint8_t MESSAGE_1           = 0;
        uint8_t MESSAGE_2           = 0;
        uint8_t MESSAGE_3           = 0;
        uint8_t MESSAGE_4           = 0;
        uint8_t NODE_POINT          = 0;
        uint8_t CPU_DONE            = 0;

    #else
        // Address value of variables are updated for RISC-V Implementation
        // inputs: 0x02000000 .. 0x0200000F
        #define ENCRYPTED_HI        (* (volatile uint32_t * ) 0x02000000)
        #define ENCRYPTED_LO        (* (volatile uint32_t * ) 0x02000004)
        #define IS_ENCRYPTED        (* (volatile uint8_t  * ) 0x02000008)
        #define NEXT_NODE           (* (volatile uint8_t  * ) 0x0200000c)
        #define CURRENT_NODE        (* (volatile uint8_t  * ) 0x0200000d)
        // outputs: 0x02000010 .. 0x0200001F
        #define MESSAGE_0           (* (volatile uint8_t  * ) 0x02000010)
        #define MESSAGE_1           (* (volatile uint8_t  * ) 0x02000011)
        #define MESSAGE_2           (* (volatile uint8_t  * ) 0x02000012)
        #define MESSAGE_3           (* (volatile uint8_t  * ) 0x02000013)
        #define MESSAGE_4           (* (volatile uint8_t  * ) 0x02000014)
        #define NODE_POINT          (* (volatile uint8_t  * ) 0x02000018)
        #define CPU_DONE            (* (volatile uint8_t  * ) 0x0200001c)

    #endif

    // read once here: for the next run, the program may write IS_ENCRYPTED = 0
    uint8_t is_encrypted = IS_ENCRYPTED;

    // the message: bytes 1..5 of the decrypted block (0x00 = no character)
    uint8_t message[5] = { 0, 0, 0, 0, 0 };

    // array to store the planned path
    uint8_t path_planned[40];
    // index to keep track of the path_planned array
    uint8_t idx = 0;

    uint8_t start_point = CURRENT_NODE;   // where the bot is
    uint8_t end_point   = 0;              // where the bot goes

    // ############# Add your code here #############

    // set path_planned[] and idx, message[] when is_encrypted = 1, and the
    // inputs for the next run (see Outputs at the top of this file)

    // prefer declaring variables like this
    #ifdef __linux__
        uint16_t dist[40];
        uint8_t parent[40];
    #else
        uint16_t *dist = (uint16_t *) 0x02000020;    // working memory starts at 0x02000020
        uint8_t *parent = (uint8_t *) 0x02000070;
    #endif

    if (is_encrypted) {
        uint64_t cipher = ((uint64_t)ENCRYPTED_HI << 32) | ENCRYPTED_LO;
        uint64_t plain = present_decrypt(cipher, ((uint64_t)PRESENT_KEY_HI << 32) | PRESENT_KEY_MID, PRESENT_KEY_LO);
        uint8_t done_flag = (uint8_t)(plain >> 56);
        message[0] = (uint8_t)(plain >> 48);
        message[1] = (uint8_t)(plain >> 40);
        message[2] = (uint8_t)(plain >> 32);
        message[3] = (uint8_t)(plain >> 24);
        message[4] = (uint8_t)(plain >> 16);
        uint8_t next_pickup = (uint8_t)(plain >> 8);
        uint8_t drop_node = (uint8_t)(plain & 0xFF);

        end_point = drop_node;

        if (done_flag == 0) {
            IS_ENCRYPTED = 0;
            CURRENT_NODE = drop_node;
            NEXT_NODE = next_pickup;
        }
    } else {
        end_point = NEXT_NODE;
    }

    if (start_point == end_point) {
        path_planned[0] = start_point;
        idx = 1;
    } else {
        for (uint8_t i = 1; i <= 36; i++) {
            dist[i] = 0xFFFF;
            parent[i] = 0;
        }
        dist[start_point] = 0;

        uint64_t visited = 0;
        for (uint8_t step = 0; step < 36; step++) {
            uint16_t min_d = 0xFFFF;
            uint8_t u = 0;
            for (uint8_t i = 1; i <= 36; i++) {
                if (!((visited >> i) & 1ULL) && dist[i] < min_d) {
                    min_d = dist[i];
                    u = i;
                }
            }
            if (u == 0 || min_d == 0xFFFF) break;
            visited |= (1ULL << u);
            if (u == end_point) break;

            uint8_t nbrs[4];
            uint8_t weights[4];
            uint8_t num_nbrs = get_neighbors(u, nbrs, weights);
            for (uint8_t k = 0; k < num_nbrs; k++) {
                uint8_t v = nbrs[k];
                uint8_t w = weights[k];
                if (!((visited >> v) & 1ULL)) {
                    uint16_t new_d = dist[u] + w;
                    if (new_d < dist[v]) {
                        dist[v] = new_d;
                        parent[v] = u;
                    }
                }
            }
        }

        uint8_t temp_path[40];
        uint8_t temp_idx = 0;
        uint8_t curr = end_point;
        while (curr != 0) {
            temp_path[temp_idx++] = curr;
            if (curr == start_point) break;
            curr = parent[curr];
        }

        idx = 0;
        while (temp_idx > 0) {
            path_planned[idx++] = temp_path[--temp_idx];
        }
    }

    // ##############################################

    // the message bytes are written into data memory (encrypted block only).
    if (is_encrypted) {
        MESSAGE_0 = message[0];
        MESSAGE_1 = message[1];
        MESSAGE_2 = message[2];
        MESSAGE_3 = message[3];
        MESSAGE_4 = message[4];
    }
    // the node values are written into data memory sequentially.
    for (int i = 0; i < idx; ++i) {
        NODE_POINT = path_planned[i];
    }
    // Path Planning Computation Done Flag
    CPU_DONE = 1;

    #ifdef __linux__    // for host pc: the output test.sh reads (see "Output (PC)" at the top)

        if (is_encrypted) {
            _put_str("Message : ");
            for (int i = 0; i < 5; ++i) {
                if (message[i]) _put_byte(message[i]);
            }
            _put_byte('\n');
        }
        for (int i = 0; i < idx; ++i) {
            _put_value(path_planned[i]);
        }
        if (is_encrypted) {
            if (IS_ENCRYPTED == 0) {            // the inputs written for the next run
                _put_str("Next current_node : ");
                _put_value(CURRENT_NODE);
                _put_str("Next next_node : ");
                _put_value(NEXT_NODE);
            }
            else {
                _put_str("Done\n");
            }
        }

    #endif

    return 0;
}

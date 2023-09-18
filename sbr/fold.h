/* fold.h -- fold a mail header field
 *
 * This code is Copyright (c) 2023, by the authors of nmh.  See the
 * COPYRIGHT file in the root directory of the nmh distribution for
 * complete copyright information. */

void fold(charstring_t dst, size_t namelen, const char *restrict body);
